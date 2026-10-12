"""Commercial and stock reports (P7-T02, P7-T03, D-113). Read-only: nothing here writes.

The sales figures come from `sales.report_rows`, the same rows the monthly closing adds up, so a report and the
closing never disagree on a dinar: revenue without VAT and cost of the goods sold, net of credit notes.
"""

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from apps.core.models import Organization
from apps.fleet import selectors as fleet
from apps.inventory import selectors as inventory
from apps.sales import selectors as sales

type GroupBy = Literal["customer", "product", "truck", "driver", "day", "week", "month"]
GROUPS: tuple[GroupBy, ...] = ("customer", "product", "truck", "driver", "day", "week", "month")
PERIODS = frozenset({"day", "week", "month"})
NO_DRIVER = "—"
ZERO = Decimal("0.000")


@dataclass(frozen=True)
class SalesLine:
    key: str
    name: str
    sales: int
    quantity: Decimal
    revenue: Decimal
    cogs: Decimal
    margin: Decimal


@dataclass(frozen=True)
class SalesReport:
    group_by: GroupBy
    date_from: dt.date
    date_to: dt.date
    rows: list[SalesLine]
    totals: SalesLine


def _week_start(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def sales_report(organization: Organization, *, group_by: GroupBy, date_from: dt.date, date_to: dt.date) -> SalesReport:
    """Confirmed sales from `date_from` to `date_to` by customer, product, truck, driver or period (day, week
    starting Monday, month), net of the credit notes issued in the period. A truck is the place the goods left
    from; the driver is the one who opened that truck's day (`—` when nobody did, or for a cold-room counter)."""
    rows = sales.report_rows(organization, date_from=date_from, date_to=date_to)
    drivers: dict[tuple[int, dt.date], str] = {}
    if group_by == "driver" and rows:
        drivers = fleet.drivers_by_truck_day(
            organization, date_from=min(r.sold_on for r in rows), date_to=max(r.sold_on for r in rows)
        )
    keys: dict[str, Callable[[sales.ReportRow], tuple[str, str]]] = {
        "customer": lambda r: (str(r.customer_id), r.customer_name),
        "product": lambda r: (str(r.product_id), r.product_name),
        "truck": lambda r: (str(r.location_id), r.location_name),
        "driver": lambda r: (
            (name := drivers.get((r.location_id, r.sold_on), NO_DRIVER)),
            name,
        ),
        "day": lambda r: (r.day.isoformat(), r.day.isoformat()),
        "week": lambda r: (_week_start(r.day).isoformat(),) * 2,
        "month": lambda r: (r.day.strftime("%Y-%m"),) * 2,
    }
    key_of = keys[group_by]
    quantity: dict[str, Decimal] = {}
    revenue: dict[str, Decimal] = {}
    cost: dict[str, Decimal] = {}
    sale_ids: dict[str, set[int]] = {}
    names: dict[str, str] = {}
    for row in rows:
        key, name = key_of(row)
        names[key] = name
        quantity[key] = quantity.get(key, ZERO) + row.quantity
        revenue[key] = revenue.get(key, ZERO) + row.revenue
        cost[key] = cost.get(key, ZERO) + row.cost
        bucket = sale_ids.setdefault(key, set())
        if not row.is_credit:
            bucket.add(row.sale_id)
    ordered = sorted(names, key=(lambda k: k) if group_by in PERIODS else (lambda k: -revenue[k]))
    lines = [
        SalesLine(k, names[k], len(sale_ids[k]), quantity[k], revenue[k], cost[k], revenue[k] - cost[k])
        for k in ordered
    ]
    all_sales = {row.sale_id for row in rows if not row.is_credit}
    total_revenue = sum((r.revenue for r in lines), ZERO)
    total_cost = sum((r.cogs for r in lines), ZERO)
    totals = SalesLine(
        "",
        "",
        len(all_sales),
        sum((r.quantity for r in lines), ZERO),
        total_revenue,
        total_cost,
        total_revenue - total_cost,
    )
    return SalesReport(group_by, date_from, date_to, lines, totals)


def stock_value(organization: Organization) -> list[inventory.LocationProductValue]:
    """Stock on hand now by place and product, at purchase cost."""
    return inventory.value_by_location_product(organization)


def slow_moving(organization: Organization, *, days: int, today: dt.date) -> list[inventory.SlowLot]:
    """Lots on hand with no movement for `days` days or more."""
    return inventory.slow_moving_lots(organization, days=days, today=today)


def losses(organization: Organization, *, date_from: dt.date, date_to: dt.date) -> list[inventory.ProductLoss]:
    """Losses and weight differences by product over the period."""
    return inventory.losses_by_product(organization, date_from=date_from, date_to=date_to)
