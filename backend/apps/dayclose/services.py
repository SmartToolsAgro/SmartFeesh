"""Every write on day closings goes through these functions (ARCHITECTURE §3)."""

import json
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core import audit
from apps.core.models import User
from apps.core.money import Number, checked_amount
from apps.fleet import selectors as fleet

from . import selectors
from .models import DayClosing, DayClosingStatus

if TYPE_CHECKING:
    from apps.fleet.models import DriverDay


def _plain(value: Any) -> Any:
    """The summary as plain JSON values: dates and Decimals become strings."""
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


@transaction.atomic
def submit_day_closing(*, driver_day: "DriverDay", actor: User, counted_cash: Number, note: str = "") -> DayClosing:
    """The driver sends the end of their day with the cash they counted. Allowed once, and again only after the
    office asked for a justification. An approved day never changes."""
    try:
        counted = checked_amount(counted_cash)
    except (ValueError, TypeError):
        raise ValidationError({"counted_cash": _("Indiquez l'argent compté, en DT, au millime près.")}) from None
    driver_day = fleet.locked_driver_day(driver_day)
    existing = selectors.closing_of(driver_day)
    if existing is not None and existing.status == DayClosingStatus.SUBMITTED:
        raise ValidationError({"counted_cash": _("Cette journée est déjà envoyée.")})
    if existing is not None and existing.status == DayClosingStatus.APPROVED:
        raise ValidationError({"counted_cash": _("Cette journée est approuvée : elle ne change plus.")})
    summary = selectors.day_summary(driver_day.organization, driver_day)
    expected: Decimal = summary["expected_cash"]
    fields: dict[str, Any] = {
        "status": DayClosingStatus.SUBMITTED,
        "expected_cash": expected,
        "counted_cash": counted,
        "difference": counted - expected,
        "driver_note": note.strip(),
        "summary": _plain(summary),
        "submitted_at": timezone.now(),
    }
    if existing is None:
        closing = DayClosing.objects.create(organization=driver_day.organization, driver_day=driver_day, **fields)
        action = "day_closing.submitted"
    else:
        for name, value in fields.items():
            setattr(existing, name, value)
        existing.save()
        closing, action = existing, "day_closing.resubmitted"
    audit.record(
        organization=closing.organization,
        actor=actor,
        action=action,
        target=closing,
        after={"expected": str(expected), "counted": str(counted), "difference": str(counted - expected)},
    )
    return closing


def _reviewable(closing: DayClosing) -> DayClosing:
    closing = DayClosing.objects.select_for_update().get(pk=closing.pk)
    if closing.status != DayClosingStatus.SUBMITTED:
        raise ValidationError(_("Seule une journée envoyée par le chauffeur peut être vérifiée."))
    return closing


@transaction.atomic
def approve_day_closing(*, closing: DayClosing, actor: User) -> DayClosing:
    """The office checked the day: it is locked."""
    closing = _reviewable(closing)
    closing.status = DayClosingStatus.APPROVED
    closing.reviewed_by = actor
    closing.reviewed_at = timezone.now()
    closing.review_note = ""
    closing.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])
    audit.record(organization=closing.organization, actor=actor, action="day_closing.approved", target=closing)
    return closing


@transaction.atomic
def request_justification(*, closing: DayClosing, actor: User, reason: str) -> DayClosing:
    """The office asks the driver to explain; the driver then sends the day again with a note."""
    if not reason.strip():
        raise ValidationError({"reason": _("Dites au chauffeur ce qu'il doit expliquer.")})
    closing = _reviewable(closing)
    closing.status = DayClosingStatus.JUSTIFICATION
    closing.reviewed_by = actor
    closing.reviewed_at = timezone.now()
    closing.review_note = reason.strip()[:300]
    closing.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])
    audit.record(
        organization=closing.organization,
        actor=actor,
        action="day_closing.justification_requested",
        target=closing,
        after={"reason": closing.review_note},
    )
    return closing
