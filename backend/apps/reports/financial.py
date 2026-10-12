"""Financial reports (P7-T04, D-116): the month's result, cash flow, what customers owe, what suppliers are owed
and unpaid salaries. Read-only, and every number comes from the selectors that already own it (the monthly closing,
the receivables, the supplier balances, the payroll), so a report never disagrees with the screen it summarises."""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from apps.closing import selectors as closing
from apps.core.models import Organization
from apps.expenses import selectors as expenses
from apps.hr import selectors as hr
from apps.partners import selectors as partners
from apps.purchasing import selectors as purchasing
from apps.sales import selectors as sales

ZERO = Decimal("0.000")
type CashGroup = Literal["day", "week", "month"]
CASH_GROUPS: tuple[CashGroup, ...] = ("day", "week", "month")


@dataclass(frozen=True)
class CategoryLine:
    name: str
    count: int
    total: Decimal


@dataclass(frozen=True)
class MonthResult:
    month: dt.date
    sales_count: int
    quantity_sold: Decimal
    revenue: Decimal
    cogs: Decimal
    gross_margin: Decimal
    spoilage: Decimal
    expenses_total: Decimal
    personnel: Decimal
    net_result: Decimal
    categories: list[CategoryLine]


def month_result(organization: Organization, *, month: dt.date) -> MonthResult:
    """The month as the monthly closing computes it, with the expenses by category."""
    report = closing.month_result(organization, month=month)
    return MonthResult(
        month=report.month,
        sales_count=report.sales_count,
        quantity_sold=report.quantity_sold,
        revenue=report.revenue,
        cogs=report.cogs,
        gross_margin=report.gross_margin,
        spoilage=report.spoilage,
        expenses_total=report.expenses_total,
        personnel=report.personnel,
        net_result=report.net_result,
        categories=[CategoryLine(c.name, c.count, c.total) for c in report.expense_categories],
    )


@dataclass(frozen=True)
class CashLine:
    key: str
    cash_in: Decimal
    cash_out: Decimal
    net: Decimal


@dataclass(frozen=True)
class CashFlow:
    date_from: dt.date
    date_to: dt.date
    group_by: CashGroup
    rows: list[CashLine]
    total_in: Decimal
    total_out: Decimal
    net: Decimal


def _bucket(day: dt.date, group_by: CashGroup) -> str:
    if group_by == "week":
        return (day - dt.timedelta(days=day.weekday())).isoformat()
    if group_by == "month":
        return day.strftime("%Y-%m")
    return day.isoformat()


def cash_flow(organization: Organization, *, date_from: dt.date, date_to: dt.date, group_by: CashGroup) -> CashFlow:
    """Money in (paid on the spot at sales, customer payments) against money out (supplier payments, salary paid,
    approved expenses) by day, week (starting Monday) or month. Money is counted on the day it moved, whatever the
    payment method; an approved expense is taken as paid on its date."""
    inflow = sales.cash_in_by_day(organization, date_from=date_from, date_to=date_to)
    outflows = (
        purchasing.payments_by_day(organization, date_from=date_from, date_to=date_to),
        hr.payments_by_day(organization, date_from=date_from, date_to=date_to),
        expenses.approved_by_day(organization, date_from=date_from, date_to=date_to),
    )
    money_in: dict[str, Decimal] = {}
    money_out: dict[str, Decimal] = {}
    for day, amount in inflow.items():
        key = _bucket(day, group_by)
        money_in[key] = money_in.get(key, ZERO) + amount
    for outflow in outflows:
        for day, amount in outflow.items():
            key = _bucket(day, group_by)
            money_out[key] = money_out.get(key, ZERO) + amount
    rows = [
        CashLine(
            key,
            money_in.get(key, ZERO),
            money_out.get(key, ZERO),
            money_in.get(key, ZERO) - money_out.get(key, ZERO),
        )
        for key in sorted(set(money_in) | set(money_out))
    ]
    total_in = sum((r.cash_in for r in rows), ZERO)
    total_out = sum((r.cash_out for r in rows), ZERO)
    return CashFlow(date_from, date_to, group_by, rows, total_in, total_out, total_in - total_out)


@dataclass(frozen=True)
class CustomerLine:
    customer_id: int
    name: str
    balance: Decimal
    overdue: Decimal
    credit: Decimal
    d0_30: Decimal
    d31_60: Decimal
    d60_plus: Decimal


@dataclass(frozen=True)
class CustomerBalances:
    rows: list[CustomerLine]
    total_balance: Decimal
    total_overdue: Decimal
    d0_30: Decimal
    d31_60: Decimal
    d60_plus: Decimal


def customer_balances(organization: Organization) -> CustomerBalances:
    """Customers who owe (biggest first) with what is overdue and the ageing 0-30, 31-60 and 61+ days. A
    customer whose credit we hold (nothing owed) is left out: this report is about money to collect."""
    names = {c.pk: c.name for c in partners.customers_of(organization, status="all")}
    rows = [
        CustomerLine(
            customer_id=customer_id,
            name=names[customer_id],
            balance=value.balance,
            overdue=value.overdue,
            credit=value.credit,
            d0_30=value.buckets.get("d0_30", ZERO),
            d31_60=value.buckets.get("d31_60", ZERO),
            d60_plus=value.buckets.get("d60_plus", ZERO),
        )
        for customer_id, value in sales.receivable_balances(organization).items()
        if customer_id in names and value.balance > 0
    ]
    rows.sort(key=lambda r: (-r.balance, r.name))
    return CustomerBalances(
        rows=rows,
        total_balance=sum((r.balance for r in rows), ZERO),
        total_overdue=sum((r.overdue for r in rows), ZERO),
        d0_30=sum((r.d0_30 for r in rows), ZERO),
        d31_60=sum((r.d31_60 for r in rows), ZERO),
        d60_plus=sum((r.d60_plus for r in rows), ZERO),
    )


@dataclass(frozen=True)
class SupplierLine:
    supplier_id: int
    name: str
    invoiced: Decimal
    paid: Decimal
    balance: Decimal
    outstanding: Decimal
    overdue: Decimal
    uninvoiced: Decimal


@dataclass(frozen=True)
class SupplierBalances:
    rows: list[SupplierLine]
    total_balance: Decimal
    total_overdue: Decimal
    total_uninvoiced: Decimal


def supplier_balances(organization: Organization) -> SupplierBalances:
    """What the company owes each supplier for goods (posted invoices minus payments), with what is overdue
    and what was received but not invoiced yet (not owed until invoiced). Partner capital and profit shares are
    other balances and never appear here (D-040)."""
    rows: list[SupplierLine] = []
    for supplier in partners.suppliers_of(organization, status="all"):
        value: Any = purchasing.supplier_balance(organization, supplier.pk)
        if value.balance == 0 and value.uninvoiced_total == 0 and value.overdue == 0:
            continue
        rows.append(
            SupplierLine(
                supplier.pk,
                supplier.name,
                value.invoiced,
                value.paid,
                value.balance,
                value.outstanding,
                value.overdue,
                value.uninvoiced_total,
            )
        )
    rows.sort(key=lambda r: (-r.balance, r.name))
    return SupplierBalances(
        rows=rows,
        total_balance=sum((r.balance for r in rows), ZERO),
        total_overdue=sum((r.overdue for r in rows), ZERO),
        total_uninvoiced=sum((r.uninvoiced for r in rows), ZERO),
    )


@dataclass(frozen=True)
class SalaryLine:
    employee_id: int
    name: str
    unpaid: Decimal


@dataclass(frozen=True)
class UnpaidSalaries:
    rows: list[SalaryLine]
    total: Decimal


def unpaid_salaries(organization: Organization) -> UnpaidSalaries:
    """What is still to pay on approved salaries, per employee (biggest first)."""
    unpaid = hr.unpaid_by_employee(organization)
    names = {e.pk: e.name for e in hr.employees_of(organization, status="all")}
    rows = [SalaryLine(key, names.get(key, "?"), amount) for key, amount in unpaid.items()]
    rows.sort(key=lambda r: (-r.unpaid, r.name))
    return UnpaidSalaries(rows, sum((r.unpaid for r in rows), ZERO))
