"""What a driver's day adds up to (P3-T06): sales, cash, expenses and the stock of the truck."""

import datetime as dt
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.core.serializers.json import DjangoJSONEncoder
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
    payments = sales.payments_received_by(organization, user_id=driver_day.driver_id, day=day)
    payments_cash = sum((p.amount for p in payments if p.method == "cash"), ZERO)
    payments_other = sum((p.amount for p in payments if p.method != "cash"), ZERO)
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
    opening: dict[int, Decimal] = {}
    for stock in inventory.location_stock_before(organization, location_id=location_id, day=day):
        names[stock["product_id"]] = stock["product__name"]
        opening[stock["product_id"]] = stock["quantity"]
    remaining: dict[int, Decimal] = {}
    for stock in inventory.location_stock(organization, location_id=location_id):
        names[stock["product_id"]] = stock["product__name"]
        remaining[stock["product_id"]] = stock["quantity"]
    products: list[dict[str, Any]] = []
    for product_id, name in sorted(names.items(), key=lambda item: item[1]):
        figures: dict[str, Any] = {
            "product_id": product_id,
            "product_name": name,
            "opening": opening.get(product_id, ZERO),
            "loaded": loaded.get(product_id, ZERO),
            "sold": sold.get(product_id, ZERO),
            "lost": lost.get(product_id, ZERO),
            "returned": returned.get(product_id, ZERO),
            "remaining": remaining.get(product_id, ZERO),
        }
        # What the day's records say should be left, against the ledger: a gap is stock that moved without a
        # sale, loss or transfer of this driver (another seller, a hand adjustment, a cancelled sale...).
        left = figures["opening"] + figures["loaded"] - figures["returned"] - figures["sold"] - figures["lost"]
        products.append({**figures, "unexplained": figures["remaining"] - left})
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


# The figures of a day that only the day's own work changes. Left out: the names, and the stock still in the truck
# (it moves again on the next days).
_DAY_FIGURES = (
    "opening_cash",
    "sales_count",
    "sales_total",
    "cash_received",
    "payments_cash",
    "other_payments",
    "on_credit",
    "expenses_total",
    "expected_cash",
)
_PRODUCT_FIGURES = ("loaded", "sold", "lost", "returned")


def _day_figures(summary: dict[str, Any]) -> dict[str, Any]:
    """The comparable part of a summary, as plain JSON values (a stored summary is already plain)."""
    plain = json.loads(json.dumps(summary, cls=DjangoJSONEncoder))
    return {
        **{name: plain.get(name) for name in _DAY_FIGURES},
        "products": {
            str(row["product_id"]): [row.get(name) for name in _PRODUCT_FIGURES]
            for row in plain.get("products", [])
            if any(Decimal(str(row.get(name) or 0)) for name in _PRODUCT_FIGURES)
        },
    }


def changed_since_sent(closing: DayClosing) -> bool:
    """The driver worked after sending the day (a new load, more sales, a payment, an expense...): the figures the
    office would check are no longer the day's. An approved day is locked, so it never counts as changed."""
    if closing.status == DayClosingStatus.APPROVED:
        return False
    sent = _day_figures(closing.summary)
    now = _day_figures(day_summary(closing.organization, closing.driver_day))
    # A summary sent before a figure existed (payments_cash, D-111) is not compared on it.
    for name in _DAY_FIGURES:
        if name not in closing.summary:
            sent.pop(name)
            now.pop(name)
    return sent != now


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


def refuse_if_day_approved(membership: Membership, on: dt.date | None = None) -> None:
    """An approved day is locked (D-094): the driver can no longer sell, spend or report losses today. With
    `on`, the day asked about is that one: a sale made on an earlier day and sent later (D-133) is refused
    when the office has already approved that day."""
    today = timezone.localdate()
    day = on or today
    approved = DayClosing.objects.for_organization(membership.organization).filter(
        driver_day__driver_id=membership.user_id,
        driver_day__date=day,
        status=DayClosingStatus.APPROVED,
    )
    if not approved.exists():
        return
    if day == today:
        raise PermissionDenied(_("Votre journée est approuvée par le bureau : elle est fermée."))
    raise PermissionDenied(
        _("Votre journée du %(day)s est approuvée par le bureau : elle est fermée, plus rien ne s'y ajoute.")
        % {"day": day.strftime("%d/%m/%Y")}
    )


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
