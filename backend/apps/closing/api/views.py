from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.closing import engine, selectors, services
from apps.closing.models import LotResult, LotResultStatus
from apps.core.models import Membership, Organization
from apps.core.permissions import ReadOwnerOrAccountantWriteOwner, membership_of
from apps.inventory import selectors as inventory

from .serializers import CloseLotSerializer, LotResultViewSerializer, ReopenLotSerializer


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
