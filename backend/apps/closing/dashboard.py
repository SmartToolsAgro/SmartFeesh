"""The owner's dashboard (P7-T01, D-104): the month so far, profit and cash kept apart, and what needs a look.

Nothing is computed here that another app already knows: the month's sales, margin and net result come
from `monthly.month_report` (the figures the accountant closes with), receivables and cash from the sales
selectors, the waiting items from the apps that own them. The month is the current one, up to today.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from apps.core.models import Organization
from apps.dayclose import selectors as dayclose
from apps.expenses import selectors as expenses
from apps.partners import selectors as partners
from apps.sales import selectors as sales

from . import monthly

ZERO = Decimal("0.000")
# Customers named in the alert; the rest are counted.
OVERDUE_SHOWN = 5


@dataclass(frozen=True)
class OverdueRow:
    customer_id: int
    name: str
    overdue: Decimal


@dataclass(frozen=True)
class Dashboard:
    month: dt.date
    # Profit (what the business earned): sales less the cost of what was sold, spoilage, expenses and payroll.
    sales: Decimal
    previous_sales: Decimal
    gross_margin: Decimal
    net_result: Decimal
    # Cash (what came in): never mixed with profit. Receivables are sales not yet paid.
    cash_collected: Decimal
    receivables: Decimal
    receivables_overdue: Decimal
    # What the company holds in stock, at cost.
    stock_value: Decimal
    # Alerts
    overdue_customers: tuple[OverdueRow, ...]
    overdue_customer_count: int
    days_waiting: int
    expenses_waiting: int


def dashboard_of(organization: Organization, *, today: dt.date) -> Dashboard:
    month = monthly.month_start(today)
    report = monthly.month_report(organization, month=month)
    previous = monthly.month_start(month - dt.timedelta(days=1))
    previous_sales = sales.month_sales(organization, date_from=previous, date_to=monthly.month_end(previous)).revenue
    receivables = sales.receivables_overview(organization, today=today)
    names = {c.pk: c.name for c in partners.customers_of(organization, status="all")}
    late = tuple(
        OverdueRow(customer_id=row.customer_id, name=names.get(row.customer_id, ""), overdue=row.overdue)
        for row in receivables.overdue_customers[:OVERDUE_SHOWN]
    )
    return Dashboard(
        month=month,
        sales=report.revenue,
        previous_sales=previous_sales,
        gross_margin=report.gross_margin,
        net_result=report.net_result,
        cash_collected=sales.cash_collected(organization, date_from=month, date_to=today),
        receivables=receivables.total,
        receivables_overdue=receivables.overdue,
        # The month-end valuation replays the ledger by date, so for this month it is the stock as of today.
        stock_value=report.closing_value,
        overdue_customers=late,
        overdue_customer_count=len(receivables.overdue_customers),
        days_waiting=dayclose.waiting_for_office(organization),
        expenses_waiting=expenses.waiting_for_approval(organization),
    )
