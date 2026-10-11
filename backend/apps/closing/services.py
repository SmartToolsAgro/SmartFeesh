"""Closing and reopening a lot: its result frozen, or unfrozen with a reason (P6-T02, D-061)."""

from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core import audit
from apps.core.locks import lock_lot
from apps.core.models import Organization, User
from apps.partnerships import selectors as partnerships
from apps.partnerships import services as partnership_services

from . import engine, selectors
from .models import LotResult, LotResultStatus


def _refusals(checks: list[selectors.ClosingCheck]) -> list[str]:
    messages = []
    for check in checks:
        if check.ok or not check.blocking:
            continue
        if check.code == "stock_empty":
            messages.append(
                _("Il reste %(quantity)s kg de ce lot en stock : vendez-les ou enregistrez une perte.")
                % {"quantity": check.quantity}
            )
        elif check.code == "costs_approved":
            messages.append(
                _("%(count)s coût(s) du lot attendent une approbation : approuvez-les ou refusez-les d'abord.")
                % {"count": check.count}
            )
        elif check.code == "customers_paid":
            messages.append(_("Des clients doivent encore %(amount)s DT sur ce lot.") % {"amount": check.amount})
    return messages


def _summary(result: LotResult) -> dict[str, Any]:
    return {
        "batch": result.batch.number,
        "status": result.status,
        "net_result": str(result.net_result),
        "partner_share": str(result.partner_share),
        "owner_share": str(result.owner_share),
        "capital_deducted": str(result.capital_deducted),
        "uncovered_loss": str(result.uncovered_loss),
    }


@transaction.atomic
def close_lot(
    *, organization: Organization, actor: User | None, batch_id: int, costs_confirmed: bool = False
) -> LotResult:
    """Close a lot: check it is finished, then freeze its result (Q19, D-040).

    Refused: a lot already closed; stock still on hand (sell it or record it as a loss); costs typed on
    the lot still waiting for approval; `costs_confirmed` not given (only the person closing knows every
    cost is in). Customers still owing money are a warning kept with the result until customer payments
    exist (P2-T06). A partner's loss share is taken from their capital in the same transaction. Two
    closings of the same lot at once: the second waits, then is refused.
    """
    lock_lot(batch_id)
    if selectors.closed_result_of(organization, batch_id=batch_id) is not None:
        raise ValidationError(_("Ce lot est déjà clôturé."))
    computed = selectors.live_result(organization, batch_id=batch_id)
    checks = selectors.closing_checks(organization, computed)
    refusals = _refusals(checks)
    if refusals:
        raise ValidationError(refusals)
    if not costs_confirmed:
        raise ValidationError({"costs_confirmed": _("Confirmez que tous les coûts du lot sont saisis.")})

    partner = computed.partner
    data = {**engine.to_json(computed), "checks": selectors.checks_to_json(checks)}
    partnership = partnerships.partnership_of(organization, partner.partnership_id) if partner is not None else None
    result = LotResult.objects.create(
        organization=organization,
        batch_id=batch_id,
        partnership=partnership,
        revenue=computed.revenue,
        cogs=computed.cogs,
        spoilage=computed.spoilage,
        costs_total=computed.costs_total,
        net_result=computed.net_result,
        owner_share=computed.owner_share,
        partner_share=partner.share if partner is not None else engine.ZERO,
        capital_deducted=partner.capital_deducted if partner is not None else engine.ZERO,
        uncovered_loss=partner.uncovered_loss if partner is not None else engine.ZERO,
        capital_to_return=partner.capital_to_return if partner is not None else engine.ZERO,
        payments_unverified=any(check.code == "customers_paid" and not check.ok for check in checks),
        data=data,
        closed_at=timezone.now(),
        closed_by=actor,
    )
    if partnership is not None and partner is not None:
        partnership_services.record_lot_closed(
            partnership=partnership,
            actor=actor,
            lot_result_id=result.pk,
            capital_deducted=partner.capital_deducted,
            on=timezone.localdate(),
        )
    audit.record(organization=organization, actor=actor, action="lot.closed", target=result, after=_summary(result))
    return result


@transaction.atomic
def reopen_lot(*, result: LotResult, actor: User | None, reason: str) -> LotResult:
    """Reopen a closed lot, with a reason (audited). Its frozen result stays as history (status
    `reopened`), the partner's deducted loss share comes back to their capital, and the next closing
    freezes a new result. A lot already settled with its partner is not reopened: a correction then
    goes to the partner's next settlement (D-041, P6-T03)."""
    lock_lot(result.batch_id)
    result = LotResult.objects.select_for_update(of=("self",)).select_related("batch").get(pk=result.pk)
    if result.status != LotResultStatus.CLOSED:
        raise ValidationError(_("Ce lot n'est pas clôturé."))
    if not reason.strip():
        raise ValidationError({"reason": _("Indiquez pourquoi le lot est rouvert.")})
    before = _summary(result)
    if result.partnership_id is not None:
        partnership = partnerships.partnership_of(result.organization, result.partnership_id)
        partnership_services.record_lot_reopened(
            partnership=partnership,
            actor=actor,
            lot_result_id=result.pk,
            capital_deducted=result.capital_deducted,
            reason=reason.strip(),
        )
    result.status = LotResultStatus.REOPENED
    result.reopened_at = timezone.now()
    result.reopened_by = actor
    result.reopen_reason = reason.strip()[:300]
    result.save(update_fields=["status", "reopened_at", "reopened_by", "reopen_reason"])
    audit.record(
        organization=result.organization,
        actor=actor,
        action="lot.reopened",
        target=result,
        before=before,
        after={**_summary(result), "reason": result.reopen_reason},
    )
    return result
