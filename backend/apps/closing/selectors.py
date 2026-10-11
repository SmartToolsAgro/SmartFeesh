"""Reads of lot results: the snapshot a result is computed from, the live result and the closing checks
(P6-T02, D-061). Every number comes from another app's selectors; nothing here writes."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import QuerySet
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core.models import Organization
from apps.expenses import selectors as expenses
from apps.hr import selectors as hr
from apps.inventory import selectors as inventory
from apps.partnerships import selectors as partnerships
from apps.sales import selectors as sales

from . import engine
from .models import LotResult, LotResultStatus

ZERO = Decimal("0.000")

# Movement kinds (inventory.MovementKind values) that write kg of a lot off or back on: the spoilage step.
WRITE_OFF_KINDS = frozenset({"loss", "count_correction", "adjustment"})
RECEIPT = "receipt"
SUPPLIER_RETURN = "supplier_return"

# Customer payments are not tracked yet (P2-T06): a sale still owed money does not stop a closing, it is
# kept as a warning with the result. P2-T06 turns this on once payments after the sale can be recorded.
CUSTOMER_PAYMENTS_BLOCK = False


def _sale_rows(organization: Organization, batch_id: int) -> tuple[engine.SaleRow, ...]:
    return tuple(
        engine.SaleRow(
            sale_id=row.line.sale_id,
            sale_number=row.line.sale.number,
            sold_on=timezone.localtime(row.line.sale.sold_at).date(),
            customer=row.line.sale.customer.name,
            quantity=row.quantity,
            unit_price=row.line.unit_price,
            revenue=row.revenue_amount,
            cost=row.cost_amount,
            amount_due=row.line.sale.amount_due,
        )
        for row in sales.batch_sales(organization, batch_id=batch_id)
    )


@dataclass(frozen=True)
class _Stock:
    received: Decimal
    returned: Decimal
    rows: tuple[engine.StockRow, ...]


def _stock(organization: Organization, batch_id: int) -> _Stock:
    """Kg received, sent back to the supplier, and written off or found, from the lot's ledger movements.
    Sales and their cancellations are read from the sales themselves; transfers stay inside the company."""
    received = returned = ZERO
    rows = []
    for movement in inventory.movements_of(organization, batch_id=batch_id).order_by("occurred_at", "id"):
        leaves = movement.from_location_id is not None and movement.to_location_id is None
        enters = movement.to_location_id is not None and movement.from_location_id is None
        if movement.kind == RECEIPT and enters:
            received += movement.quantity
        elif movement.kind == SUPPLIER_RETURN and leaves:
            returned += movement.quantity
        elif movement.kind in WRITE_OFF_KINDS and (leaves or enters):
            rows.append(
                engine.StockRow(
                    movement_id=movement.pk,
                    kind=movement.kind,
                    occurred_on=timezone.localtime(movement.occurred_at).date(),
                    quantity=movement.quantity if leaves else -movement.quantity,
                    unit_cost=movement.unit_cost,
                    reason=movement.reason,
                )
            )
    return _Stock(received=received, returned=returned, rows=tuple(rows))


def _expense_cost_row(line: Any) -> engine.CostRow:
    """One line of `expenses.lot_cost_lines`, whatever its kind: the lot's own expenses, its truck-day
    shares, and the cold-room and general costs that P5-T02/T05 add, without a change here."""
    expense_id = getattr(line, "expense_id", None) or None
    quantity, day_quantity = getattr(line, "quantity", None), getattr(line, "day_quantity", None)
    place = getattr(line, "truck_name", "") or getattr(line, "location_name", "")
    month = getattr(line, "month", None)
    parts = [place] if place else []
    if quantity is not None and day_quantity is not None:
        parts.append(f"{quantity} / {day_quantity} kg")
    if month is not None:
        parts.append(month.strftime("%m/%Y"))
    if getattr(line, "estimated", False):
        parts.append(_("estimation"))
    detail = " · ".join(parts)
    return engine.CostRow(
        kind=str(line.kind),
        on=line.spent_on,
        title=getattr(line, "category_name", "") or str(line.kind),
        amount=line.amount,
        description=getattr(line, "description", ""),
        source_type="expense" if expense_id else "",
        source_id=expense_id,
        reference=getattr(line, "expense_number", ""),
        detail=detail,
    )


def _cost_rows(organization: Organization, batch_id: int) -> tuple[engine.CostRow, ...]:
    """The lot's approved costs: `expenses.lot_cost_lines` (all its kinds) and its employees' days (hr)."""
    lines = [
        line
        for line in expenses.lot_cost_lines(organization, batch_id=batch_id)
        if line.status == "approved"  # lot_cost_lines gives approved lines only by default; kept explicit
    ]
    rows = [_expense_cost_row(line) for line in lines]
    rows += [
        engine.CostRow(
            kind="employee",
            on=day.work_date,
            title=day.employee.name,
            amount=day.cost,
            description=day.notes,
            source_type="employee",
            source_id=day.employee_id,
            detail=f"{day.days} × {day.monthly_salary} / 26",
        )
        for day in hr.lot_work_days_of(organization, batch_id=batch_id).order_by("work_date", "id")
    ]
    return tuple(rows)


def _terms(organization: Organization, batch_id: int) -> engine.PartnershipTerms | None:
    partnership = partnerships.live_partnership_of_batch(organization, batch_id=batch_id)
    if partnership is None:
        return None
    return engine.PartnershipTerms(
        partnership_id=partnership.pk,
        partner_id=partnership.partner_id,
        partner_name=partnership.partner.name,
        owner_capital=partnership.owner_capital,
        partner_capital=partnerships.capital_put_in(partnership),
        profit_rate=partnership.profit_rate,
        loss_rate=partnership.loss_rate,
    )


def lot_snapshot(organization: Organization, *, batch_id: int) -> engine.LotSnapshot:
    """Everything the result of one lot is computed from, read now. Raises Batch.DoesNotExist outside the
    organization."""
    batch = inventory.batch_of(organization, batch_id)
    stock = _stock(organization, batch_id)
    return engine.LotSnapshot(
        batch_id=batch.pk,
        batch_number=batch.number,
        product_name=batch.product.name,
        supplier_name=batch.supplier.name,
        received_on=batch.received_on,
        unit_cost=batch.unit_cost,
        received_quantity=stock.received,
        returned_quantity=stock.returned,
        on_hand_quantity=inventory.quantity_on_hand(organization, batch_id=batch_id),
        sales=_sale_rows(organization, batch_id),
        stock_rows=stock.rows,
        costs=_cost_rows(organization, batch_id),
        partnership=_terms(organization, batch_id),
    )


def live_result(organization: Organization, *, batch_id: int) -> engine.ComputedResult:
    """The lot's result now: "so far" on an open lot, what a closing would freeze on a finished one."""
    return engine.lot_result(lot_snapshot(organization, batch_id=batch_id))


# ---- Closing checks ----


@dataclass(frozen=True)
class ClosingCheck:
    """One condition of closing a lot (Q19: sold out, costs in, customers paid)."""

    code: str
    ok: bool
    # A failed blocking check refuses the closing; a failed warning is kept with the result.
    blocking: bool
    quantity: Decimal | None = None
    count: int | None = None
    amount: Decimal | None = None


def closing_checks(organization: Organization, result: engine.ComputedResult) -> list[ClosingCheck]:
    """What stands between the lot and its closing, with the figures the screen explains it with."""
    snapshot = result.snapshot
    waiting = [
        line
        for line in expenses.lot_cost_lines(organization, batch_id=snapshot.batch_id, approved_only=False)
        if line.status != "approved"
    ]
    owed = {sale.sale_id: sale.amount_due for sale in snapshot.sales if sale.amount_due > 0}
    return [
        # Stock 0: everything sold, sent back or written off as a loss.
        ClosingCheck(
            code="stock_empty",
            ok=snapshot.on_hand_quantity == 0,
            blocking=True,
            quantity=snapshot.on_hand_quantity,
        ),
        # Costs typed on the lot but not approved yet would be left out of the frozen result.
        ClosingCheck(
            code="costs_approved",
            ok=not waiting,
            blocking=True,
            count=len(waiting),
            amount=sum((line.amount for line in waiting), ZERO),
        ),
        # Customers paid (Q19): known only for the payment on the spot until P2-T06.
        ClosingCheck(
            code="customers_paid",
            ok=not owed,
            blocking=CUSTOMER_PAYMENTS_BLOCK,
            count=len(owed),
            amount=sum(owed.values(), ZERO),
        ),
    ]


def checks_to_json(checks: list[ClosingCheck]) -> list[dict[str, Any]]:
    return [
        {
            "code": check.code,
            "ok": check.ok,
            "blocking": check.blocking,
            "quantity": None if check.quantity is None else str(check.quantity),
            "count": check.count,
            "amount": None if check.amount is None else str(check.amount),
        }
        for check in checks
    ]


# ---- Frozen results ----


def results_of(organization: Organization, *, batch_id: int | None = None) -> QuerySet[LotResult]:
    """Lot results, newest closing first, closed and reopened ones."""
    results = LotResult.objects.for_organization(organization).select_related(
        "batch__product", "partnership__partner", "closed_by", "reopened_by"
    )
    if batch_id is not None:
        results = results.filter(batch_id=batch_id)
    return results.order_by("-closed_at", "-id")


def closed_result_of(organization: Organization, *, batch_id: int) -> LotResult | None:
    """The frozen result of a closed lot; None while the lot is open (or was reopened)."""
    return results_of(organization, batch_id=batch_id).filter(status=LotResultStatus.CLOSED).first()


def closed_batch_ids(organization: Organization, *, batch_ids: list[int] | None = None) -> set[int]:
    """The lots that are closed now, among `batch_ids` (all when None)."""
    results = LotResult.objects.for_organization(organization).filter(status=LotResultStatus.CLOSED)
    if batch_ids is not None:
        results = results.filter(batch_id__in=batch_ids)
    return set(results.values_list("batch_id", flat=True))
