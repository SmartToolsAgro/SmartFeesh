"""What a driver's day adds up to (P3-T06): sales, cash, expenses and the stock of the truck."""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.exceptions import PermissionDenied

from apps.core.models import Membership, Organization
from apps.expenses import selectors as expenses
from apps.inventory import selectors as inventory
from apps.sales import selectors as sales

from .models import DayClosing, DayClosingStatus, SyncProblem

if TYPE_CHECKING:
    from apps.fleet.models import DriverDay

ZERO = Decimal("0.000")


def day_summary(organization: Organization, driver_day: "DriverDay") -> dict[str, Any]:
    """The day's figures for this driver on this truck, computed from the records."""
    day = driver_day.date
    location_id = driver_day.truck.location_id
    day_sales = list(
        sales.sales_of(
            organization,
            status="confirmed",
            location_id=location_id,
            created_by_id=driver_day.driver_id,
            date_from=day,
            date_to=day,
        )
    )
    cash = sum((s.amount_paid for s in day_sales if s.payment_method == "cash"), ZERO)
    paid = sum((s.amount_paid for s in day_sales), ZERO)
    spent = sum(
        (
            e.amount
            for e in expenses.road_expenses(organization, user_id=driver_day.driver_id, day=day)
            if e.status != "rejected"
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
    for row in inventory.truck_day(organization, location_id=location_id, day=day):
        names[row.product_id] = row.product_name
        loaded[row.product_id] = row.loaded
        returned[row.product_id] = row.returned
    lost: dict[int, Decimal] = {}
    for loss in inventory.losses_of(organization, status="approved", location_id=location_id):
        if loss.lost_on == day:
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
        "other_payments": paid - cash,
        "on_credit": sum((s.amount_due for s in day_sales), ZERO),
        "expenses_total": spent,
        "expected_cash": driver_day.opening_cash + cash - spent,
        "products": products,
    }


def closing_of(driver_day: "DriverDay") -> DayClosing | None:
    return DayClosing.objects.filter(driver_day=driver_day).first()


def closings_of(organization: Organization, *, status: str | None = None) -> QuerySet[DayClosing]:
    """Closings newest first, with the day, the truck and the driver."""
    rows = (
        DayClosing.objects.for_organization(organization)
        .select_related("driver_day__truck__location", "driver_day__driver", "reviewed_by")
        .order_by("-submitted_at", "-id")
    )
    return rows.filter(status=status) if status else rows


def closing_by_id(organization: Organization, closing_id: int) -> DayClosing:
    return closings_of(organization).get(pk=closing_id)


def refuse_if_day_approved(membership: Membership) -> None:
    """An approved day is locked (D-094): the driver can no longer sell, spend or report losses today."""
    approved = DayClosing.objects.for_organization(membership.organization).filter(
        driver_day__driver_id=membership.user_id,
        driver_day__date=timezone.localdate(),
        status=DayClosingStatus.APPROVED,
    )
    if approved.exists():
        raise PermissionDenied(_("Votre journée est approuvée par le bureau : elle est fermée."))


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
