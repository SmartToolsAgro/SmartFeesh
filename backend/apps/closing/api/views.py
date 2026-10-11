from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.closing import engine, selectors, services
from apps.closing.models import LotResult, LotResultStatus, SettlementState
from apps.core.models import Membership, Organization
from apps.core.permissions import ReadOwnerOrAccountantWriteOwner, membership_of
from apps.inventory import selectors as inventory
from apps.partners import selectors as suppliers
from apps.partnerships import selectors as partnerships

from .serializers import (
    CloseLotSerializer,
    LotResultViewSerializer,
    LotSettlementViewSerializer,
    PartnerBalancesSerializer,
    ReopenLotSerializer,
    SettleLotSerializer,
)


def person_name(user: Any) -> str:
    if user is None:
        return ""
    return f"{user.first_name} {user.last_name}".strip() or user.username


def _closing(result: LotResult) -> dict[str, Any]:
    return {
        "id": result.pk,
        "status": result.status,
        "net_result": result.net_result,
        "closed_at": result.closed_at,
        "closed_by_name": person_name(result.closed_by),
        "payments_unverified": result.payments_unverified,
        "reopened_at": result.reopened_at,
        "reopened_by_name": person_name(result.reopened_by),
        "reopen_reason": result.reopen_reason,
    }


def lot_result_payload(organization: Organization, batch_id: int) -> dict[str, Any]:
    """The lot's result for the screen: frozen when the lot is closed, live otherwise, with the checks."""
    computed = selectors.live_result(organization, batch_id=batch_id)
    results = list(selectors.results_of(organization, batch_id=batch_id))
    closed = next((result for result in results if result.status == LotResultStatus.CLOSED), None)
    history = [_closing(result) for result in results if result.status == LotResultStatus.REOPENED]
    if closed is not None:
        return {
            "batch_id": batch_id,
            "state": "closed",
            "result": closed.data,
            "checks": closed.data.get("checks", []),
            "can_close": False,
            "closing": _closing(closed),
            "live_net_result": computed.net_result,
            "history": history,
        }
    checks = selectors.closing_checks(organization, computed)
    return {
        "batch_id": batch_id,
        "state": "open",
        "result": engine.to_json(computed),
        "checks": selectors.checks_to_json(checks),
        "can_close": all(check.ok or not check.blocking for check in checks),
        "closing": None,
        "live_net_result": None,
        "history": history,
    }


# A lot's result shows its margin and the partner's share: the owner's business (D-061). The owner reads,
# closes and reopens; the accountant reads; managers and drivers get 403 (provisional).
# A comment, not a docstring: a docstring would describe every endpoint in the schema.
class LotResultBaseView(APIView):
    permission_classes = (ReadOwnerOrAccountantWriteOwner,)

    @property
    def membership(self) -> Membership:
        membership = membership_of(self.request)
        assert membership is not None  # guaranteed by the permission class
        return membership

    @property
    def organization(self) -> Organization:
        return self.membership.organization

    def check_batch(self, batch_id: int) -> None:
        try:
            inventory.batch_of(self.organization, batch_id)
        except ObjectDoesNotExist:
            raise Http404 from None

    def answer(self, batch_id: int) -> Response:
        return Response(LotResultViewSerializer(lot_result_payload(self.organization, batch_id)).data)


class LotResultView(LotResultBaseView):
    @extend_schema(operation_id="getLotResult", responses=LotResultViewSerializer)
    def get(self, request: Request, batch_id: int) -> Response:
        """The result of one lot with every step: revenue, purchase cost of the kg sold, kg written off,
        each kind of cost, net result, and on a partnership lot the partner's share, the loss share taken
        from their capital and the capital to give back. Live ("so far") on an open lot, frozen on a
        closed one, with what closing the lot needs."""
        self.check_batch(batch_id)
        return self.answer(batch_id)


class CloseLotView(LotResultBaseView):
    @extend_schema(operation_id="closeLot", request=CloseLotSerializer, responses=LotResultViewSerializer)
    def post(self, request: Request, batch_id: int) -> Response:
        """Close the lot and freeze its result (owner only): its stock must be 0 (sold or written off),
        its costs approved, and `costs_confirmed` given. A partner's loss share is taken from their capital."""
        self.check_batch(batch_id)
        serializer = CloseLotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.close_lot(
            organization=self.organization,
            actor=self.membership.user,
            batch_id=batch_id,
            costs_confirmed=serializer.validated_data["costs_confirmed"],
        )
        return self.answer(batch_id)


def _settlement_record(settlement: Any) -> dict[str, Any]:
    return {
        "id": settlement.pk,
        "settled_on": settlement.settled_on,
        "capital_returned": settlement.capital_returned,
        "lot_share": settlement.lot_share,
        "uncovered_loss": settlement.uncovered_loss,
        "carried_in": settlement.carried_in,
        "share_paid": settlement.share_paid,
        "amount_paid": settlement.amount_paid,
        "carried_out": settlement.carried_out,
        "notes": settlement.notes,
        "created_by_name": person_name(settlement.created_by),
        "payments": list(settlement.payments.all()),
    }


def partner_balances_payload(organization: Organization, partner_id: int, partner_name: str) -> dict[str, Any]:
    balances = partnerships.partner_balances(organization, partner_id=partner_id)
    return {
        "partner_id": partner_id,
        "partner_name": partner_name,
        "trade_payable": balances.trade_payable,
        "capital": balances.capital,
        "profit_share": balances.profit_share,
        "lots": balances.lots,
    }


def lot_settlement_payload(organization: Organization, batch_id: int) -> dict[str, Any]:
    """Where the lot stands with its partner: what settling would pay, or what was paid, the late costs
    waiting for the next settlement, and the partner's three balances."""
    partnership = partnerships.live_partnership_of_batch(organization, batch_id=batch_id)
    empty: dict[str, Any] = {
        "batch_id": batch_id,
        "state": SettlementState.NONE,
        "partnership_id": None,
        "partner_id": None,
        "partner_name": "",
        "preview": None,
        "settlement": None,
        "late": None,
        "entries": [],
        "balances": None,
    }
    if partnership is None:
        return empty
    payload = {
        **empty,
        "partnership_id": partnership.pk,
        "partner_id": partnership.partner_id,
        "partner_name": partnership.partner.name,
        "entries": list(partnerships.profit_share_entries_of(partnership)),
        "balances": partner_balances_payload(organization, partnership.partner_id, partnership.partner.name),
        "state": SettlementState.NOT_CLOSED,
    }
    result = selectors.closed_result_of(organization, batch_id=batch_id)
    if result is None:
        return payload
    drift = selectors.late_drift(organization, result)
    if drift is not None:
        payload["late"] = {
            "drift": drift.drift,
            "booked": drift.booked,
            "pending_basis": drift.pending_basis,
            "pending_share": drift.pending_share,
        }
    settlement = partnerships.settlement_of(partnership)
    if settlement is not None:
        payload["state"] = SettlementState.SETTLED
        payload["settlement"] = _settlement_record(settlement)
    else:
        payload["state"] = SettlementState.READY
        payload["preview"] = selectors.settlement_preview(organization, result)
    return payload


class LotSettlementView(LotResultBaseView):
    @extend_schema(operation_id="getLotSettlement", responses=LotSettlementViewSerializer)
    def get(self, request: Request, batch_id: int) -> Response:
        """The lot's settlement with its partner: what settling would pay (capital back ± share, minus what
        the partner owes from earlier lots), or what was paid; the late costs waiting for the next
        settlement; and the partner's three balances (trade payable, capital, profit share)."""
        self.check_batch(batch_id)
        return Response(LotSettlementViewSerializer(lot_settlement_payload(self.organization, batch_id)).data)


class SettleLotView(LotResultBaseView):
    @extend_schema(operation_id="settleLot", request=SettleLotSerializer, responses=LotSettlementViewSerializer)
    def post(self, request: Request, batch_id: int) -> Response:
        """Settle a closed partnership lot with its partner (owner only): pay their capital back and their
        profit share. The payments must add up to the amount shown by `getLotSettlement`."""
        self.check_batch(batch_id)
        serializer = SettleLotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.settle_lot(
            organization=self.organization,
            actor=self.membership.user,
            batch_id=batch_id,
            payments=[dict(payment) for payment in serializer.validated_data.get("payments", [])],
            notes=serializer.validated_data["notes"],
        )
        return Response(LotSettlementViewSerializer(lot_settlement_payload(self.organization, batch_id)).data)


class BookLateAdjustmentsView(LotResultBaseView):
    @extend_schema(operation_id="bookLateAdjustments", request=None, responses=LotSettlementViewSerializer)
    def post(self, request: Request, batch_id: int) -> Response:
        """Carry the costs recorded after the lot closed to the partner's balance now (owner only), without
        reopening the lot. Settling does it too; this makes the amount visible on the partner's balance."""
        self.check_batch(batch_id)
        services.book_late_adjustments(organization=self.organization, actor=self.membership.user, batch_id=batch_id)
        return Response(LotSettlementViewSerializer(lot_settlement_payload(self.organization, batch_id)).data)


class PartnerBalancesView(LotResultBaseView):
    @extend_schema(operation_id="getPartnerBalances", responses=PartnerBalancesSerializer)
    def get(self, request: Request, partner_id: int) -> Response:
        """A partner's three balances, kept apart: what is owed for goods (trade payable), their capital
        still in lots, and their profit share (owed to them, or by them)."""
        try:
            partner = suppliers.supplier_of(self.organization, partner_id)
        except ObjectDoesNotExist:
            raise Http404 from None
        return Response(
            PartnerBalancesSerializer(partner_balances_payload(self.organization, partner.pk, partner.name)).data
        )


class ReopenLotView(LotResultBaseView):
    @extend_schema(operation_id="reopenLot", request=ReopenLotSerializer, responses=LotResultViewSerializer)
    def post(self, request: Request, batch_id: int) -> Response:
        """Reopen a closed lot (owner only, reason required, audited). The frozen result stays as history."""
        self.check_batch(batch_id)
        serializer = ReopenLotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = selectors.closed_result_of(self.organization, batch_id=batch_id)
        if result is None:
            raise Http404
        services.reopen_lot(result=result, actor=self.membership.user, reason=serializer.validated_data["reason"])
        return self.answer(batch_id)
