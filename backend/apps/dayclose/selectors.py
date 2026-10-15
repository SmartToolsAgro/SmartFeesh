"""What a driver's day adds up to (P3-T06): sales, cash, expenses and the stock of the truck."""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db.models import Q, QuerySet, Sum
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.exceptions import PermissionDenied

from apps.core.models import Membership, Organization
from apps.expenses import selectors as expenses
from apps.fleet import selectors as fleet
from apps.inventory import selectors as inventory
from apps.purchasing import selectors as purchasing
from apps.sales import selectors as sales

from .models import DayClosing, DayClosingStatus, DayReopening, SyncProblem

if TYPE_CHECKING:
    from apps.fleet.models import DriverDay

ZERO = Decimal("0.000")


def day_summary(organization: Organization, driver_day: "DriverDay") -> dict[str, Any]:
    """The figures of one driver's day on its truck, computed from the records, over the day's own window
    (`fleet.day_window`, D-134): its date, up to the moment the closing was sent.

    A sale counts when it was made inside the window (`sold_at`, D-133), also when it reached the server
    later. Customer payments and road expenses count when they were recorded (they are dated when they are
    sent). The stock is read from the ledger on one clock (`occurred_at`): what the truck held when the day
    started (`opening`), what was loaded, returned and lost during it, and what it held when it ended
    (`remaining`; while the day runs, what it holds now). So opening + loaded - returned - sold - lost is what
    is left, and `unexplained` is only stock that moved without a sale of this driver, a loss or a transfer.

    `handed_over` is the cash counted at the sends a new load undid (`DayReopening`): it went to the office, so
    `expected_cash` is what the driver should hold now, not the day's whole cash."""
    day = driver_day.date
    location_id = driver_day.truck.location_id
    start, end = fleet.day_window(driver_day)

    def inside(moment: dt.datetime) -> bool:
        return start <= moment < end

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
        if inside(sale.sold_at)
    ]
    cash = sum((s.amount_paid for s in day_sales if s.payment_method == "cash"), ZERO)
    paid = sum((s.amount_paid for s in day_sales), ZERO)
    payments = [
        p
        for p in sales.payments_received_by(organization, user_id=driver_day.driver_id, day=day)
        if inside(p.made_at or p.created_at)
    ]
    payments_cash = sum((p.amount for p in payments if p.method == "cash"), ZERO)
    payments_other = sum((p.amount for p in payments if p.method != "cash"), ZERO)
    spent = sum(
        (
            e.amount
            for e in expenses.road_expenses(organization, user_id=driver_day.driver_id, day=day)
            if e.status != "rejected" and inside(e.made_at or e.created_at)
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
    lost: dict[int, Decimal] = {}
    for moves in inventory.location_moves_between(organization, location_id=location_id, start=start, end=end):
        names[moves.product_id] = moves.product_name
        loaded[moves.product_id] = moves.loaded
        returned[moves.product_id] = moves.returned
        lost[moves.product_id] = moves.lost
    opening: dict[int, Decimal] = {}
    for stock in inventory.location_stock_at(organization, location_id=location_id, moment=start):
        names[stock["product_id"]] = stock["product__name"]
        opening[stock["product_id"]] = stock["quantity"]
    # Left in the truck: what it holds now while the day's window is open, what the ledger held when it closed
    # otherwise (the driver's next day has moved the stock since).
    left_now = end > timezone.now()
    left_rows = (
        inventory.location_stock(organization, location_id=location_id)
        if left_now
        else inventory.location_stock_at(organization, location_id=location_id, moment=end)
    )
    remaining: dict[int, Decimal] = {}
    for stock in left_rows:
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
    # Purchases at the port (D-158): the cash given comes out of the purchase money first, kept apart; what goes
    # beyond it was paid with the sales cash. Cheques and traites are not cash.
    bought = purchasing.purchases_paid_between(organization, buyer_id=driver_day.driver_id, start=start, end=end)
    purchase_money = driver_day.purchase_float - handed_over_purchase_of(driver_day)
    from_sales = max(bought.cash - purchase_money, ZERO)
    driver = driver_day.driver
    handed_over = handed_over_of(driver_day)
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
        "handed_over": handed_over,
        "expected_cash": driver_day.opening_cash + cash + payments_cash - spent - handed_over - from_sales,
        "purchase_float": driver_day.purchase_float,
        "purchases_count": bought.count,
        "purchases_total": bought.total,
        "purchases_cash": bought.cash,
        "purchases_other": bought.other,
        "purchases_from_sales": from_sales,
        "expected_purchase_cash": max(purchase_money - bought.cash, ZERO),
        "products": products,
    }


def handed_over_of(driver_day: "DriverDay") -> Decimal:
    """The cash the driver already gave the office that day: what was counted at each send that a new load
    undid (D-134)."""
    total: Decimal | None = DayReopening.objects.filter(closing__driver_day=driver_day).aggregate(
        total=Sum("counted_cash")
    )["total"]
    return total if total is not None else ZERO


def handed_over_purchase_of(driver_day: "DriverDay") -> Decimal:
    """The purchase money the driver already gave back to the office that day: what was counted of it at each
    send a new load undid (D-158, as `handed_over_of` for the sales cash)."""
    total: Decimal | None = DayReopening.objects.filter(closing__driver_day=driver_day).aggregate(
        total=Sum("counted_purchase_cash")
    )["total"]
    return total if total is not None else ZERO


def closing_of(driver_day: "DriverDay") -> DayClosing | None:
    return DayClosing.objects.filter(driver_day=driver_day).first()


def day_answer(organization: Organization, driver_day: "DriverDay") -> dict[str, Any]:
    """A driver's day as the phone shows it: the figures as sent once the closing is sent (they do not move,
    D-134), the day's records before. The records are shown again whenever the driver is about to send again,
    since they are what the new send will keep: the office asked for a justification, a new load reopened the
    day, or the records no longer say what was sent (D-132)."""
    closing = closing_of(driver_day)
    as_sent = closing is not None and (
        closing.status == DayClosingStatus.APPROVED
        or (closing.status == DayClosingStatus.SUBMITTED and not changed_since_sent(closing))
    )
    summary = closing.summary if closing is not None and as_sent else day_summary(organization, driver_day)
    return {"summary": summary, "closing": closing}


# The figures compared between a closing as sent and the day's records now: of the day, then per product.
DAY_FIGURES = (
    "sales_count",
    "sales_total",
    "cash_received",
    "payments_cash",
    "other_payments",
    "on_credit",
    "expenses_total",
    "expected_cash",
    "purchases_cash",
    "purchases_other",
    "expected_purchase_cash",
)
PRODUCT_FIGURES = ("opening", "loaded", "sold", "lost", "returned", "remaining")
CHANGED_FIGURES = (*DAY_FIGURES, *PRODUCT_FIGURES)


def changes_since_sent(closing: DayClosing) -> list[dict[str, Any]]:
    """Where the day's records, read now, no longer say what the driver sent (D-134): one row per figure that
    differs, with the value as sent and the value now; `product_name` is empty for a figure of the whole day.

    A sent closing never changes by itself. A sale made before it was sent and received after it (D-133) is
    still recorded on that day while the office has not approved it, as is anything the office corrects
    afterwards (an expense rejected, a sale cancelled): the snapshot keeps what was sent and this list shows
    the office the difference. Empty when nothing moved, for an approved closing, which is locked, and for a
    reopened day, whose send is undone. A figure the snapshot does not have (an older closing) is not
    compared."""
    if closing.status in (DayClosingStatus.APPROVED, DayClosingStatus.REOPENED):
        return []
    sent: dict[str, Any] = closing.summary
    live = day_summary(closing.organization, closing.driver_day)
    rows: list[dict[str, Any]] = []

    def compare(figure: str, product_name: str, before: Any, after: Any) -> None:
        before, after = Decimal(str(before)), Decimal(str(after))
        if before != after:
            rows.append({"figure": figure, "product_name": product_name, "sent": before, "live": after})

    for figure in DAY_FIGURES:
        if figure in sent:
            compare(figure, "", sent[figure], live[figure])
    sent_products = {row["product_id"]: row for row in sent.get("products", [])}
    live_products = {row["product_id"]: row for row in live["products"]}
    # A figure no sent product has is one the snapshot was made without (opening, before D-130).
    known = [f for f in PRODUCT_FIGURES if not sent_products or any(f in row for row in sent_products.values())]
    names = {row["product_id"]: row["product_name"] for row in (*sent_products.values(), *live_products.values())}
    for product_id, name in sorted(names.items(), key=lambda item: (item[1], item[0])):
        before_row = sent_products.get(product_id, {})
        after_row = live_products.get(product_id, {})
        for figure in known:
            compare(figure, name, before_row.get(figure, ZERO), after_row.get(figure, ZERO))
    return rows


def changed_since_sent(closing: DayClosing) -> bool:
    """The day's records no longer say what the driver sent (D-132): the office waits for the day sent again."""
    return bool(changes_since_sent(closing))


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
        .prefetch_related("reopenings__reviewed_by", "reopenings__load")
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


def _closed_day() -> PermissionDenied:
    return PermissionDenied(_("Votre journée est clôturée : elle rouvre quand le bureau recharge votre camion."))


def refuse_if_day_closed(membership: Membership) -> None:
    """Once the driver sent the closing, the day is over (D-134, replaces D-109): nothing more is spent, lost,
    returned or collected on it, until a load validated that date opens it again. (A sale has its own check,
    on the moment it was made: `refuse_sale_outside_day`.)"""
    driver_day = fleet.driver_day_of(membership)
    if driver_day is not None and driver_day.ended_at is not None:
        raise _closed_day()


def refuse_sale_outside_day(membership: Membership, made_at: dt.datetime | None = None) -> None:
    """Whether a driver's sale may still be recorded, from the moment it was made (now by default; `made_at`
    is the phone's time once checked, D-133) and the driver's day of that date (D-134).

    Refused with 403 when:
    - the day had already ended at that moment: the sale was made after the closing was sent, and only a load
      validated that date opens the day again;
    - the day is approved by the office (D-094): nothing is added to it.
    A day sent but not approved still takes a sale made before it was sent: the figures the driver sent stay
    as sent, and the office waits for the day sent again (`changes_since_sent`, D-132).
    No day started on that date: accepted, the sale belongs to no closing (D-133)."""
    moment = made_at or timezone.now()
    today = timezone.localdate()
    day = timezone.localtime(moment).date()
    driver_day = fleet.driver_day_of(membership, day)
    if driver_day is None:
        return
    if driver_day.ended_at is not None and moment >= driver_day.ended_at:
        if day == today:
            raise _closed_day()
        raise PermissionDenied(
            _(
                "Votre journée du %(day)s était déjà clôturée quand cette vente a été faite : "
                "elle n'est pas enregistrée. Prévenez le bureau."
            )
            % {"day": day.strftime("%d/%m/%Y")}
        )
    approved = DayClosing.objects.for_organization(membership.organization).filter(
        driver_day=driver_day, status=DayClosingStatus.APPROVED
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


# A closing the office has nothing to do on: checked already, or running again until its driver sends it.
_NOT_WITH_THE_OFFICE = (DayClosingStatus.APPROVED, DayClosingStatus.REOPENED)


def waiting_for_office(organization: Organization) -> int:
    """Driver days sent by the driver (or sent again with a note) and not approved yet. A day a new load
    reopened waits for its driver, not for the office."""
    return closings_of(organization).exclude(status__in=_NOT_WITH_THE_OFFICE).count()


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
    the driver left no note, or the office asked for a justification and has not got it. Newest first. Not a
    reopened day: its difference is that of the send a new load undid, and its next count is still to come."""
    rows = (
        closings_of(organization)
        .exclude(status__in=_NOT_WITH_THE_OFFICE)
        .exclude(difference=0, purchase_difference=0)
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
            # Both boxes: the sales cash and the purchase money (D-158).
            difference=row.difference + row.purchase_difference,
        )
        for row in rows
    ]
