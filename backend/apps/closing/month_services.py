"""Reviewing, approving and reopening a month (P6-T06, D-074).

The accountant reviews, the owner approves: approval freezes the figures. Nothing here changes a lot or a
partner's share (those are settled per lot, D-040).
"""

import datetime as dt
import hashlib
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core import audit
from apps.core.models import Organization, User

from . import month_selectors, monthly
from .models import MonthlyClosing, MonthlyClosingStatus


def fingerprint_of(report: monthly.MonthReport) -> str:
    """The figures an approval stands on: if any moves after the review, the review no longer holds."""
    parts = [
        report.revenue,
        report.cogs,
        report.spoilage,
        report.expenses_total,
        report.personnel,
        report.net_result,
        report.closing_value,
        report.opening_value,
    ]
    return hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()


def _summary(closing: MonthlyClosing) -> dict[str, Any]:
    return {
        "month": closing.month.isoformat(),
        "status": closing.status,
        "net_result": str(closing.net_result),
        "revenue": str(closing.revenue),
        "closing_stock_value": str(closing.closing_stock_value),
    }


def checked_month(month: dt.date) -> dt.date:
    """The first day of a month that is over: the current month cannot be closed."""
    first = monthly.month_start(month)
    if monthly.month_end(first) >= timezone.localdate():
        raise ValidationError(_("Ce mois n'est pas terminé : il se clôture après son dernier jour."))
    return first


def _refusals(report: monthly.MonthReport) -> list[str]:
    messages = {
        "expenses_approved": _("Des dépenses du mois attendent encore une décision."),
        "payroll_approved": _("Des salaires du mois sont encore des brouillons."),
        "losses_decided": _("Des pertes du mois attendent encore la décision du propriétaire."),
    }
    return [
        messages[check.code] for check in report.checks if check.blocking and not check.ok and check.code in messages
    ]


@transaction.atomic
def review_month(*, organization: Organization, actor: User | None, month: dt.date, notes: str = "") -> MonthlyClosing:
    """The accountant (or the owner) checks the month's figures. Refused while expenses, salaries or losses
    of the month wait for a decision. Reviewing again replaces an earlier review that was not approved."""
    first = checked_month(month)
    existing = month_selectors.live_closing_of(organization, month=first, for_update=True)
    if existing is not None and existing.status == MonthlyClosingStatus.APPROVED:
        raise ValidationError(_("Ce mois est déjà approuvé : le propriétaire doit d'abord le rouvrir."))
    report = monthly.month_report(organization, month=first)
    refusals = _refusals(report)
    if refusals:
        raise ValidationError(refusals)
    data = monthly.to_json(report)
    fields: dict[str, Any] = {
        "status": MonthlyClosingStatus.REVIEWED,
        "revenue": report.revenue,
        "cogs": report.cogs,
        "spoilage": report.spoilage,
        "operating_costs": report.operating_costs,
        "net_result": report.net_result,
        "closing_stock_value": report.closing_value,
        "data": data,
        "fingerprint": fingerprint_of(report),
        "reviewed_at": timezone.now(),
        "reviewed_by": actor,
        "review_notes": notes.strip()[:300],
    }
    if existing is not None:
        # A review replaces an earlier, unapproved one: a plain save (the queryset refuses bulk updates).
        for name, value in fields.items():
            setattr(existing, name, value)
        existing.save()
        closing = existing
    else:
        closing = MonthlyClosing.objects.create(organization=organization, month=first, **fields)
    audit.record(
        organization=organization, actor=actor, action="month.reviewed", target=closing, after=_summary(closing)
    )
    return closing


@transaction.atomic
def approve_month(*, organization: Organization, actor: User | None, month: dt.date) -> MonthlyClosing:
    """The owner approves a reviewed month: its figures are frozen as they are now. Refused when the month
    was not reviewed, or when the figures moved since the review (a late expense, a sale...)."""
    first = checked_month(month)
    closing = month_selectors.live_closing_of(organization, month=first, for_update=True)
    if closing is None:
        raise ValidationError(_("Le comptable doit d'abord vérifier ce mois."))
    if closing.status == MonthlyClosingStatus.APPROVED:
        raise ValidationError(_("Ce mois est déjà approuvé."))
    report = monthly.month_report(organization, month=first)
    refusals = _refusals(report)
    if refusals:
        raise ValidationError(refusals)
    if fingerprint_of(report) != closing.fingerprint:
        raise ValidationError(
            _("Les chiffres du mois ont changé depuis la vérification : le comptable doit la refaire.")
        )
    before = _summary(closing)
    closing.status = MonthlyClosingStatus.APPROVED
    closing.data = monthly.to_json(report)
    closing.approved_at = timezone.now()
    closing.approved_by = actor
    closing.save()
    audit.record(
        organization=organization,
        actor=actor,
        action="month.approved",
        target=closing,
        before=before,
        after=_summary(closing),
    )
    return closing


@transaction.atomic
def reopen_month(*, organization: Organization, actor: User | None, month: dt.date, reason: str) -> MonthlyClosing:
    """The owner reopens a reviewed or approved month, with a reason (audited). The frozen copy stays as
    history; a new review and approval make a new one."""
    first = monthly.month_start(month)
    closing = month_selectors.live_closing_of(organization, month=first, for_update=True)
    if closing is None:
        raise ValidationError(_("Ce mois n'est ni vérifié ni approuvé."))
    if not reason.strip():
        raise ValidationError({"reason": _("Indiquez pourquoi le mois est rouvert.")})
    before = _summary(closing)
    closing.status = MonthlyClosingStatus.REOPENED
    closing.reopened_at = timezone.now()
    closing.reopened_by = actor
    closing.reopen_reason = reason.strip()[:300]
    closing.save()
    audit.record(
        organization=organization,
        actor=actor,
        action="month.reopened",
        target=closing,
        before=before,
        after={**_summary(closing), "reason": closing.reopen_reason},
    )
    return closing
