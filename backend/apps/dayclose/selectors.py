"""What a driver's day adds up to (P3-T06): sales, cash, expenses and the stock of the truck."""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db.models import Q, QuerySet
from django.utils.translation import gettext as _
from rest_framework.exceptions import PermissionDenied

from apps.core.models import Membership, Organization
from apps.expenses import selectors as expenses
from apps.fleet import selectors as fleet
from apps.inventory import selectors as inventory
from apps.sales import selectors as sales

from .models import DayClosing, DayClosingStatus, SyncProblem

if TYPE_CHECKING:
    from apps.fleet.models import DriverDay

ZERO = Decimal("0.000")


def day_summary(organization: Organization, driver_day: "DriverDay") -> dict[str, Any]:
    """The day's figures for this driver on this truck, computed from the records. A driver who opens a second day
    on the same date splits the date: each day counts what was recorded within its window (D-126)."""
    day = driver_day.date
    location_id = driver_day.truck.location_id
    start, end = fleet.day_window(driver_day)

    def inside(moment: dt.datetime) -> bool:
        return (start is None or moment >= start) and (end is None or moment < end)

    day_sales = [
        sale
        for sale in sales.sales_of(
            organization,
            status="confirmed",
            location_id=location_id,
            created_by_id=driver_day.driver_id,
            date_from=day,
            date_to=day,
        )
        if inside(sale.created_at)
    ]
    cash = sum((s.amount_paid for s in day_sales if s.payment_method == "cash"), ZERO)
    paid = sum((s.amount_paid for s in day_sales), ZERO)
    payments = [
        p
        for p in sales.payments_received_by(organization, user_id=driver_day.driver_id, day=day)
        if inside(p.created_at)
    ]
    payments_cash = sum((p.amount for p in payments if p.method == "cash"), ZERO)
    payments_other = sum((p.amount for p in payments if p.method != "cash"), ZERO)
    spent = sum(
        (
            e.amount
            for e in expenses.road_expenses(organization, user_id=driver_day.driver_id, day=day)
            if e.status != "rejected" and inside(e.created_at)
        ),
        ZERO,
    )
    names: dict[int, str] = {}
    sold: dict[int, Decimal] = {}
    for sale in day_sales:
        for line in sale.lines.all():
            names[line.product_id] = line.product.name
            sold[line.product_id] = sold.get(line.product_id, ZERO) + line.quantity
    loaded: dict[int, Decimal] = {}
    returned: dict[int, Decimal] = {}
    for row in inventory.truck_day(
        organization, location_id=location_id, day=day, validated_after=start, validated_before=end
    ):
        names[row.product_id] = row.product_name
        loaded[row.product_id] = row.loaded
        returned[row.product_id] = row.returned
    lost: dict[int, Decimal] = {}
    for loss in inventory.losses_of(organization, status="approved", location_id=location_id):
        if loss.lost_on == day and inside(loss.created_at):
            names[loss.product_id] = loss.product.name
            lost[loss.product_id] = lost.get(loss.product_id, ZERO) + loss.quantity
    remaining: dict[int, Decimal] = {}
    for stock in inventory.location_stock(organization, location_id=location_id):
        names[stock["product_id"]] = stock["product__name"]
        remaining[stock["product_id"]] = stock["quantity"]
    products = [
        {
            "product_id": product_id,
            "product_name": name,
            "loaded": loaded.get(product_id, ZERO),
            "sold": sold.get(product_id, ZERO),
            "lost": lost.get(product_id, ZERO),
            "returned": returned.get(product_id, ZERO),
            "remaining": remaining.get(product_id, ZERO),
        }
        for product_id, name in sorted(names.items(), key=lambda item: item[1])
    ]
    driver = driver_day.driver
    return {
        "date": day,
        "truck_name": driver_day.truck.location.name,
        "driver_name": f"{driver.first_name} {driver.last_name}".strip() or driver.username,
        "opening_cash": driver_day.opening_cash,
        "sales_count": len(day_sales),
        "sales_total": sum((s.total for s in day_sales), ZERO),
        "cash_received": cash,
        "payments_cash": payments_cash,
        "other_payments": paid - cash + payments_other,
        "on_credit": sum((s.amount_due for s in day_sales), ZERO),
        "expenses_total": spent,
        "expected_cash": driver_day.opening_cash + cash + payments_cash - spent,
        "products": products,
    }


def closing_of(driver_day: "DriverDay") -> DayClosing | None:
    return DayClosing.objects.filter(driver_day=driver_day).first()


def day_answer(organization: Organization, driver_day: "DriverDay") -> dict[str, Any]:
    """A driver's day as the phone shows it: the figures as sent once the closing is sent, live before."""
    closing = closing_of(driver_day)
    summary = closing.summary if closing is not None else day_summary(organization, driver_day)
    return {"summary": summary, "closing": closing}


def closings_of(
    organization: Organization,
    *,
    status: str | None = None,
    search: str = "",
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> QuerySet[DayClosing]:
    """Closings newest first, with the day, the truck and the driver; the office's history of the drivers' days."""
    rows = (
        DayClosing.objects.for_organization(organization)
        .select_related("driver_day__truck__location", "driver_day__driver", "reviewed_by")
        .order_by("-submitted_at", "-id")
    )
    if status:
        rows = rows.filter(status=status)
    if search := search.strip():
        rows = rows.filter(
            Q(driver_day__driver__first_name__icontains=search)
            | Q(driver_day__driver__last_name__icontains=search)
            | Q(driver_day__driver__username__icontains=search)
            | Q(driver_day__truck__location__name__icontains=search)
        )
    if date_from is not None:
        rows = rows.filter(driver_day__date__gte=date_from)
    if date_to is not None:
        rows = rows.filter(driver_day__date__lte=date_to)
    return rows


def closing_by_id(organization: Organization, closing_id: int) -> DayClosing:
    return closings_of(organization).get(pk=closing_id)


def refuse_if_day_closed(membership: Membership) -> None:
    """Once the driver sent the closing, the day is over (D-126, replaces D-109): nothing more is sold, spent or
    lost on it. The driver starts another day first."""
    driver_day = fleet.driver_day_of(membership)
    if driver_day is not None and driver_day.ended_at is not None:
        raise PermissionDenied(_("Votre journée est clôturée : commencez une nouvelle journée."))


def sync_problems_of(organization: Organization, *, open_only: bool = True) -> QuerySet[SyncProblem]:
    """Refused sends reported by the phones, newest first."""
    rows = SyncProblem.objects.for_organization(organization).select_related("driver", "resolved_by")
    return rows.filter(resolved_at__isnull=True) if open_only else rows


def sync_problem_by_id(organization: Organization, problem_id: int) -> SyncProblem:
    return sync_problems_of(organization, open_only=False).get(pk=problem_id)


def waiting_for_office(organization: Organization) -> int:
    """Driver days sent by the driver (or sent again with a note) and not approved yet."""
    return closings_of(organization).exclude(status=DayClosingStatus.APPROVED).count()


# ---- Alert for the owner's dashboard (P7-T07, D-114) ----


@dataclass(frozen=True)
class CashDifference:
    closing_id: int
    day: dt.date
    driver_name: str
    # counted - expected: negative means less cash than the records say.
    difference: Decimal


def unexplained_cash_differences(organization: Organization) -> list[CashDifference]:
    """Driver days not approved yet whose counted cash is not what the records say and that nobody explained:
    the driver left no note, or the office asked for a justification and has not got it. Newest first."""
    rows = (
        closings_of(organization)
        .exclude(status=DayClosingStatus.APPROVED)
        .exclude(difference=0)
        .filter(Q(driver_note="") | Q(status=DayClosingStatus.JUSTIFICATION))
        .order_by("-driver_day__date", "-id")
    )
    return [
        CashDifference(
            closing_id=row.pk,
            day=row.driver_day.date,
            driver_name=(
                f"{row.driver_day.driver.first_name} {row.driver_day.driver.last_name}".strip()
                or row.driver_day.driver.username
            ),
            difference=row.difference,
        )
        for row in rows
    ]
