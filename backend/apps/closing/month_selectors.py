"""Reads of monthly closings (P6-T06, D-074)."""

import datetime as dt

from django.db.models import QuerySet

from apps.core.models import Organization

from .models import MonthlyClosing, MonthlyClosingStatus, MonthState

LIVE = (MonthlyClosingStatus.REVIEWED, MonthlyClosingStatus.APPROVED)


def closings_of(organization: Organization, *, month: dt.date | None = None) -> QuerySet[MonthlyClosing]:
    """Every review and approval, reopened ones too, newest month first."""
    rows = MonthlyClosing.objects.for_organization(organization).select_related(
        "reviewed_by", "approved_by", "reopened_by"
    )
    if month is not None:
        rows = rows.filter(month=month.replace(day=1))
    return rows.order_by("-month", "-id")


def live_closing_of(organization: Organization, *, month: dt.date, for_update: bool = False) -> MonthlyClosing | None:
    """The month's reviewed or approved closing (there is at most one), or None."""
    rows = MonthlyClosing.objects.for_organization(organization).filter(month=month.replace(day=1), status__in=LIVE)
    if for_update:
        rows = rows.select_for_update()
    return rows.first()


def state_of(closing: MonthlyClosing | None) -> str:
    if closing is None:
        return MonthState.OPEN
    return MonthState.APPROVED if closing.status == MonthlyClosingStatus.APPROVED else MonthState.REVIEWED
