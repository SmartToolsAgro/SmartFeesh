"""Reusable read queries of sales documents."""

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import (
    Case,
    CharField,
    Count,
    DecimalField,
    Exists,
    F,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.core.models import Organization

from .models import (
    CreditNote,
    CreditNoteLine,
    CreditNoteLineBatch,
    CustomerPayment,
    FinanceSettings,
    Invoice,
    InvoiceLine,
    InvoiceSale,
    InvoiceStatus,
    InvoiceVatLine,
    Quote,
    QuoteLine,
    QuoteStatus,
    Sale,
    SaleLine,
    SaleLineBatch,
    SaleStatus,
)

# ---- Quotes (P2-T03, D-050) ----


def current_quote_status(today: dt.date) -> Case:
    """The status a quote shows on `today`: a sent quote whose validity date has passed is expired, even
    before the nightly `expire_quotes` writes it down."""
    return Case(
        When(status=QuoteStatus.SENT, valid_until__lt=today, then=Value(QuoteStatus.EXPIRED.value)),
        default=F("status"),
        output_field=CharField(),
    )


def quotes_of(
    organization: Organization,
    *,
    status: str | None = None,
    customer_id: int | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    search: str = "",
    today: dt.date | None = None,
) -> QuerySet[Quote]:
    """Quotes newest first, each with `current_status` (see `current_quote_status`), `line_count`, its
    customer, location and lines (product). `status` filters on the current status; `search` matches the
    number and the customer's name or reference."""
    today = today or timezone.localdate()
    lines = QuoteLine.objects.select_related("product").order_by("id")
    quotes = (
        Quote.objects.for_organization(organization)
        .select_related("customer", "location", "created_by", "sent_by", "answered_by")
        .prefetch_related(Prefetch("lines", queryset=lines))
        .prefetch_related(
            Prefetch(
                "sales",
                queryset=Sale.objects.exclude(status=SaleStatus.CANCELLED).order_by("-id"),
                to_attr="live_sales",
            )
        )
        .annotate(current_status=current_quote_status(today), line_count=Count("lines"))
        .order_by("-quoted_on", "-id")
    )
    if status:
        quotes = quotes.filter(current_status=status)
    if customer_id is not None:
        quotes = quotes.filter(customer_id=customer_id)
    if date_from is not None:
        quotes = quotes.filter(quoted_on__gte=date_from)
    if date_to is not None:
        quotes = quotes.filter(quoted_on__lte=date_to)
    if search := search.strip():
        quotes = quotes.filter(
            Q(number__icontains=search) | Q(customer__name__icontains=search) | Q(customer__reference__icontains=search)
        )
    return quotes


def quote_of(organization: Organization, quote_id: int) -> Quote:
    """One quote with its lines. Raises Quote.DoesNotExist outside the organization."""
    return quotes_of(organization).get(pk=quote_id)


def quotes_to_expire(organization: Organization, *, today: dt.date) -> QuerySet[Quote]:
    """Sent quotes whose validity date is before `today`: the customer never answered."""
    return Quote.objects.for_organization(organization).filter(status=QuoteStatus.SENT, valid_until__lt=today)


def live_sale_of(quote: Quote) -> "Sale | None":
    """The sale an accepted quote became, unless it was cancelled (P2-T04, D-051)."""
    sales: list[Sale] | None = getattr(quote, "live_sales", None)  # prefetched by `quotes_of`
    if sales is None:
        sales = list(quote.sales.exclude(status=SaleStatus.CANCELLED).order_by("-id"))
    return sales[0] if sales else None


# ---- Sales (P2-T04, D-051) ----


def sales_of(
    organization: Organization,
    *,
    status: str | None = None,
    customer_id: int | None = None,
    location_id: int | None = None,
    created_by_id: int | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    search: str = "",
    uninvoiced: bool = False,
) -> QuerySet[Sale]:
    """Sales newest first, each with `line_count`, its customer, place, quote and lines (product, batches).
    Days are those of `sold_at` in local time, both included; `search` matches the number and the
    customer's name or reference. `uninvoiced`: the BL still to invoice (confirmed, of a named customer,
    on no live invoice)."""
    lines = (
        SaleLine.objects.select_related("product")
        .prefetch_related(Prefetch("batches", queryset=SaleLineBatch.objects.select_related("batch").order_by("id")))
        .order_by("id")
    )
    sales = (
        Sale.objects.for_organization(organization)
        .select_related(
            "customer", "location", "quote", "created_by", "confirmed_by", "cancelled_by", "credit_decided_by"
        )
        .prefetch_related(Prefetch("lines", queryset=lines))
        .prefetch_related(
            Prefetch(
                "invoices",
                queryset=Invoice.objects.exclude(status=InvoiceStatus.CANCELLED).order_by("-id"),
                to_attr="live_invoices",
            )
        )
        .annotate(line_count=Count("lines"))
        .order_by("-sold_at", "-id")
    )
    if status:
        sales = sales.filter(status=status)
    if customer_id is not None:
        sales = sales.filter(customer_id=customer_id)
    if location_id is not None:
        sales = sales.filter(location_id=location_id)
    if created_by_id is not None:
        sales = sales.filter(created_by_id=created_by_id)
    if date_from is not None:
        sales = sales.filter(sold_at__date__gte=date_from)
    if date_to is not None:
        sales = sales.filter(sold_at__date__lte=date_to)
    if uninvoiced:
        sales = sales.filter(status=SaleStatus.CONFIRMED, customer__is_walk_in=False).exclude(
            Exists(InvoiceSale.objects.filter(sale=OuterRef("pk"), is_live=True))
        )
    if search := search.strip():
        sales = sales.filter(
            Q(number__icontains=search) | Q(customer__name__icontains=search) | Q(customer__reference__icontains=search)
        )
    return sales


def sale_of(organization: Organization, sale_id: int) -> Sale:
    """One sale with its lines and their batches. Raises Sale.DoesNotExist outside the organization."""
    return sales_of(organization).get(pk=sale_id)


def returned_by_sale_batch(sale_line_batch_ids: Iterable[int]) -> dict[int, Decimal]:
    """Kilos credit notes already took back, per sale line batch id (customer returns, D-070)."""
    rows = (
        CreditNoteLineBatch.objects.filter(sale_line_batch_id__in=list(sale_line_batch_ids))
        .values("sale_line_batch_id")
        .annotate(quantity=Sum("quantity"))
        .order_by("sale_line_batch_id")
    )
    return {row["sale_line_batch_id"]: row["quantity"] for row in rows}


def _credit_sum(field: str) -> Coalesce:
    """What the credit notes took back of `field`, for the sale line batch row being read."""
    subquery = (
        CreditNoteLineBatch.objects.filter(sale_line_batch_id=OuterRef("pk"))
        .values("sale_line_batch_id")
        .annotate(total=Sum(field))
        .values("total")
    )
    return Coalesce(
        Subquery(subquery, output_field=DecimalField(max_digits=14, decimal_places=3)),
        Value(Decimal("0.000")),
        output_field=DecimalField(max_digits=14, decimal_places=3),
    )


@dataclass(frozen=True)
class NetSale:
    """What a `batch_sales` row still counts after the credit notes: kg, revenue and cost of goods."""

    quantity: Decimal
    revenue: Decimal
    cost: Decimal


def net_of(row: SaleLineBatch) -> NetSale:
    """A row of `batch_sales` net of what credit notes took back of it (D-070)."""
    annotated: Any = row  # the three annotations of `batch_sales`
    return NetSale(
        quantity=row.quantity - annotated.returned_quantity,
        revenue=row.revenue_amount - annotated.credited_revenue,
        cost=row.cost_amount - annotated.returned_cost,
    )


def batch_sales(organization: Organization, *, batch_id: int) -> QuerySet[SaleLineBatch]:
    """What one lot (batch) sold, line by line, oldest sale first: confirmed sales only (a cancelled sale's
    kilos came back). Each row has its line (price, product) and sale (number, moment, customer, place), and
    what credit notes took back of it: `returned_quantity`, `credited_revenue`, `returned_cost` (D-070)."""
    return (
        SaleLineBatch.objects.for_organization(organization)
        .filter(batch_id=batch_id, line__sale__status=SaleStatus.CONFIRMED)
        .annotate(
            returned_quantity=_credit_sum("quantity"),
            credited_revenue=_credit_sum("revenue_amount"),
            returned_cost=_credit_sum("cost_amount"),
        )
        .select_related("line__product", "line__sale__customer", "line__sale__location", "batch")
        .order_by("line__sale__sold_at", "line__sale_id", "id")
    )


@dataclass(frozen=True)
class BatchSalesTotal:
    """What one lot sold over its confirmed sales: kg, revenue without VAT and cost of the goods (COGS)."""

    batch_id: int
    quantity: Decimal
    revenue: Decimal
    cost: Decimal

    @property
    def margin(self) -> Decimal:
        return self.revenue - self.cost


def batch_sales_totals(
    organization: Organization, *, batch_ids: Iterable[int] | None = None
) -> dict[int, BatchSalesTotal]:
    """Kg sold, revenue and cost of goods per lot (batch id), over confirmed sales, net of what credit notes
    took back (D-070): the sales side of a lot's result (D-040; Phase 6 adds the lot's own costs). Lots that
    sold nothing are left out."""
    rows = SaleLineBatch.objects.for_organization(organization).filter(line__sale__status=SaleStatus.CONFIRMED)
    if batch_ids is not None:
        rows = rows.filter(batch_id__in=list(batch_ids))
    totals = rows.values("batch_id").annotate(
        quantity=Sum("quantity"), revenue=Sum("revenue_amount"), cost=Sum("cost_amount")
    )
    credits = CreditNoteLineBatch.objects.for_organization(organization).filter(
        sale_line_batch__line__sale__status=SaleStatus.CONFIRMED
    )
    if batch_ids is not None:
        credits = credits.filter(sale_line_batch__batch_id__in=list(batch_ids))
    credited = {
        row["sale_line_batch__batch_id"]: row
        for row in credits.values("sale_line_batch__batch_id").annotate(
            quantity=Sum("quantity"), revenue=Sum("revenue_amount"), cost=Sum("cost_amount")
        )
    }
    zero = Decimal("0.000")
    result = {}
    for row in totals.order_by("batch_id"):
        back = credited.get(row["batch_id"])
        result[row["batch_id"]] = BatchSalesTotal(
            batch_id=row["batch_id"],
            quantity=row["quantity"] - (back["quantity"] if back else zero),
            revenue=row["revenue"] - (back["revenue"] if back else zero),
            cost=row["cost"] - (back["cost"] if back else zero),
        )
    return result


# ---- Finance settings (P2-T05, D-056) ----


def finance_settings_history(organization: Organization) -> QuerySet[FinanceSettings]:
    """Every version of the finance settings, the latest start first (planned ones included)."""
    return (
        FinanceSettings.objects.for_organization(organization)
        .select_related("created_by")
        .order_by("-valid_from", "-id")
    )


def finance_settings_on(organization: Organization, day: dt.date | None = None) -> FinanceSettings | None:
    """The version in force on `day` (today by default): the latest one that started on or before it. None
    only before the first version (every organization gets one when created, D-056)."""
    day = day or timezone.localdate()
    return finance_settings_history(organization).filter(valid_from__lte=day).first()


# ---- Invoices and credit notes (P2-T05, D-057) ----


def live_invoice_of(sale: Sale) -> Invoice | None:
    """The sale's invoice, draft or issued, unless it was cancelled by a credit note."""
    invoices: list[Invoice] | None = getattr(sale, "live_invoices", None)  # prefetched by `sales_of`
    if invoices is None:
        invoices = list(sale.invoices.exclude(status=InvoiceStatus.CANCELLED).order_by("-id"))
    return invoices[0] if invoices else None


def invoices_of(
    organization: Organization,
    *,
    status: str | None = None,
    customer_id: int | None = None,
    sale_id: int | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    search: str = "",
) -> QuerySet[Invoice]:
    """Invoices, drafts first then the newest issued, each with its sale, customer, lines, VAT per rate and
    credit notes, and `credited_total` (what its credit notes gave back, net). Days are the issue dates, both
    included (a draft has none and is left out by a day filter); `search` matches the number, the sale's
    number and the customer's name or reference."""
    credit_lines = CreditNoteLine.objects.select_related("invoice_line").order_by("id")
    credit_notes = (
        CreditNote.objects.select_related("created_by")
        .prefetch_related(Prefetch("lines", queryset=credit_lines))
        .order_by("id")
    )
    invoices = (
        Invoice.objects.for_organization(organization)
        .select_related("organization", "customer", "settings_version", "created_by", "issued_by")
        .prefetch_related(Prefetch("sales", queryset=Sale.objects.order_by("sold_at", "id")))
        .prefetch_related(
            Prefetch("lines", queryset=InvoiceLine.objects.select_related("product", "sale_line__sale").order_by("id"))
        )
        .prefetch_related(Prefetch("vat_lines", queryset=InvoiceVatLine.objects.order_by("-rate")))
        .prefetch_related(Prefetch("credit_notes", queryset=credit_notes))
        .prefetch_related("certificates")
        .annotate(
            line_count=Count("lines", distinct=True),
            credited_total=Coalesce(
                Subquery(
                    CreditNote.objects.filter(invoice=OuterRef("pk"))
                    .values("invoice")
                    .annotate(total=Sum("net_amount"))
                    .values("total")
                ),
                Value(Decimal("0.000")),
                output_field=DecimalField(max_digits=14, decimal_places=3),
            ),
        )
        .order_by(F("issued_on").desc(nulls_first=True), "-id")
    )
    if status:
        invoices = invoices.filter(status=status)
    if customer_id is not None:
        invoices = invoices.filter(customer_id=customer_id)
    if sale_id is not None:
        invoices = invoices.filter(Exists(InvoiceSale.objects.filter(invoice=OuterRef("pk"), sale_id=sale_id)))
    if date_from is not None:
        invoices = invoices.filter(issued_on__gte=date_from)
    if date_to is not None:
        invoices = invoices.filter(issued_on__lte=date_to)
    if search := search.strip():
        invoices = invoices.filter(
            Q(number__icontains=search)
            | Exists(InvoiceSale.objects.filter(invoice=OuterRef("pk"), sale__number__icontains=search))
            | Q(customer__name__icontains=search)
            | Q(customer__reference__icontains=search)
        )
    return invoices


def invoice_of(organization: Organization, invoice_id: int) -> Invoice:
    """One invoice with everything it prints. Raises Invoice.DoesNotExist outside the organization."""
    return invoices_of(organization).get(pk=invoice_id)


@dataclass(frozen=True)
class CreditedLine:
    """What the credit notes already gave back on one invoice line."""

    quantity: Decimal
    amount_excl_tax: Decimal
    vat_amount: Decimal


def credited_by_line(invoice: Invoice) -> dict[int, CreditedLine]:
    """Kilos and amounts already given back per invoice line id, over the invoice's credit notes."""
    rows = (
        CreditNoteLine.objects.filter(credit_note__invoice=invoice)
        .values("invoice_line_id")
        .annotate(quantity=Sum("quantity"), excl=Sum("amount_excl_tax"), vat=Sum("vat_amount"))
        .order_by("invoice_line_id")
    )
    return {
        row["invoice_line_id"]: CreditedLine(
            quantity=row["quantity"], amount_excl_tax=row["excl"], vat_amount=row["vat"]
        )
        for row in rows
    }


def credit_notes_of(
    organization: Organization,
    *,
    customer_id: int | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    search: str = "",
) -> QuerySet[CreditNote]:
    """Credit notes, newest first, each with its invoice (and customer) and lines."""
    notes = (
        CreditNote.objects.for_organization(organization)
        .select_related("invoice", "invoice__customer", "created_by")
        .prefetch_related(Prefetch("lines", queryset=CreditNoteLine.objects.select_related("invoice_line")))
        .order_by("-issued_on", "-id")
    )
    if customer_id is not None:
        notes = notes.filter(invoice__customer_id=customer_id)
    if date_from is not None:
        notes = notes.filter(issued_on__gte=date_from)
    if date_to is not None:
        notes = notes.filter(issued_on__lte=date_to)
    if search := search.strip():
        notes = notes.filter(
            Q(number__icontains=search)
            | Q(invoice__number__icontains=search)
            | Q(invoice__customer__name__icontains=search)
        )
    return notes


# ---- Receivables for other apps (P2-T06, D-062) ----


def outstanding_by_sale(organization: Organization, sale_ids: list[int]) -> dict[int, Decimal]:
    """What customers still owe on the given confirmed sales, by sale id (only the sales with something left):
    after payments, credit notes and withholding. The "customers paid" check of lot closing reads it (D-068)."""
    from . import receivables  # receivables imports models only; kept local to avoid a cycle with selectors

    rows = receivables.sale_receivables(organization, sale_ids=sale_ids)
    return {row.sale_id: row.outstanding for row in rows if row.outstanding > 0}


# ---- Month figures (P6-T05, D-073) ----


@dataclass(frozen=True)
class MonthSales:
    """What a period sold, from the sale-line snapshots (never from purchases): revenue without VAT and the
    cost of the goods sold (COGS), each net of what credit notes took back in the period."""

    sales: int
    quantity: Decimal
    revenue: Decimal
    cogs: Decimal
    # What credit notes issued in the period took back (already taken off the figures above).
    credited_revenue: Decimal
    returned_cost: Decimal


def month_sales(organization: Organization, *, date_from: dt.date, date_to: dt.date) -> MonthSales:
    """Confirmed sales made from `date_from` to `date_to` (local days, inclusive): revenue and COGS from their
    batch rows, less the revenue and cost credit notes issued in the same days gave back. A sale cancelled
    later no longer counts (its kilos came back)."""
    start = timezone.make_aware(dt.datetime.combine(date_from, dt.time.min))
    end = timezone.make_aware(dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time.min))
    zero = Decimal("0.000")
    sold = SaleLineBatch.objects.for_organization(organization).filter(
        line__sale__status=SaleStatus.CONFIRMED, line__sale__sold_at__gte=start, line__sale__sold_at__lt=end
    )
    totals = sold.aggregate(quantity=Sum("quantity"), revenue=Sum("revenue_amount"), cost=Sum("cost_amount"))
    count = (
        Sale.objects.for_organization(organization)
        .filter(status=SaleStatus.CONFIRMED, sold_at__gte=start, sold_at__lt=end)
        .count()
    )
    credited = CreditNoteLineBatch.objects.for_organization(organization).filter(
        line__credit_note__issued_on__gte=date_from,
        line__credit_note__issued_on__lte=date_to,
        sale_line_batch__line__sale__status=SaleStatus.CONFIRMED,
    )
    back = credited.aggregate(quantity=Sum("quantity"), revenue=Sum("revenue_amount"), cost=Sum("cost_amount"))
    credited_revenue = back["revenue"] or zero
    returned_cost = back["cost"] or zero
    return MonthSales(
        sales=count,
        quantity=(totals["quantity"] or zero) - (back["quantity"] or zero),
        revenue=(totals["revenue"] or zero) - credited_revenue,
        cogs=(totals["cost"] or zero) - returned_cost,
        credited_revenue=credited_revenue,
        returned_cost=returned_cost,
    )


@dataclass(frozen=True)
class ReportRow:
    """One slice of what was sold (or given back by a credit note) for the commercial reports: the kilos,
    revenue without VAT and cost of one sale line batch. A credit note's row carries negative figures."""

    sale_id: int
    day: dt.date
    sold_on: dt.date
    customer_id: int
    customer_name: str
    product_id: int
    product_name: str
    location_id: int
    location_name: str
    quantity: Decimal
    revenue: Decimal
    cost: Decimal
    is_credit: bool


def report_rows(organization: Organization, *, date_from: dt.date, date_to: dt.date) -> list[ReportRow]:
    """The rows `month_sales` adds up, one per sale line batch, so every report agrees with the closing
    (D-113): confirmed sales made from `date_from` to `date_to`, and, with negative figures, what credit notes
    issued in those days gave back. `day` is the day the row counts in (sale day, or credit note day);
    `sold_on` is always the sale's own day."""
    start = timezone.make_aware(dt.datetime.combine(date_from, dt.time.min))
    end = timezone.make_aware(dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time.min))
    fields = (
        "line__sale_id",
        "line__sale__sold_at",
        "line__sale__customer_id",
        "line__sale__customer__name",
        "line__product_id",
        "line__product__name",
        "line__sale__location_id",
        "line__sale__location__name",
        "quantity",
        "revenue_amount",
        "cost_amount",
    )
    rows: list[ReportRow] = []
    sold = (
        SaleLineBatch.objects.for_organization(organization)
        .filter(line__sale__status=SaleStatus.CONFIRMED, line__sale__sold_at__gte=start, line__sale__sold_at__lt=end)
        .order_by("id")
        .values_list(*fields)
    )
    for sale_id, sold_at, customer_id, customer, product_id, product, location_id, location, kg, revenue, cost in sold:
        local_day = timezone.localtime(sold_at).date()
        rows.append(
            ReportRow(
                sale_id,
                local_day,
                local_day,
                customer_id,
                customer,
                product_id,
                product,
                location_id,
                location,
                kg,
                revenue,
                cost,
                False,
            )
        )
    given_back = (
        CreditNoteLineBatch.objects.for_organization(organization)
        .filter(
            line__credit_note__issued_on__gte=date_from,
            line__credit_note__issued_on__lte=date_to,
            sale_line_batch__line__sale__status=SaleStatus.CONFIRMED,
        )
        .order_by("id")
        .values_list(
            "line__credit_note__issued_on",
            *(f"sale_line_batch__{name}" for name in fields[:8]),
            "quantity",
            "revenue_amount",
            "cost_amount",
        )
    )
    for (
        issued_on,
        sale_id,
        sold_at,
        customer_id,
        customer,
        product_id,
        product,
        location_id,
        location,
        kg,
        revenue,
        cost,
    ) in given_back:
        rows.append(
            ReportRow(
                sale_id,
                issued_on,
                timezone.localtime(sold_at).date(),
                customer_id,
                customer,
                product_id,
                product,
                location_id,
                location,
                -kg,
                -revenue,
                -cost,
                True,
            )
        )
    return rows


def draft_sales_count(organization: Organization, *, date_from: dt.date, date_to: dt.date) -> int:
    """Sales still drafts, dated in the period: they have not left the stock nor counted anywhere."""
    start = timezone.make_aware(dt.datetime.combine(date_from, dt.time.min))
    end = timezone.make_aware(dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time.min))
    return (
        Sale.objects.for_organization(organization)
        .filter(status=SaleStatus.DRAFT, sold_at__gte=start, sold_at__lt=end)
        .count()
    )


def recent_customer_ids(organization: Organization, *, user_id: int, limit: int = 8) -> list[int]:
    """The customers this person sold to most recently, most recent first (the walk-in customer included)."""
    seen: list[int] = []
    rows = (
        Sale.objects.for_organization(organization)
        .filter(created_by_id=user_id, status="confirmed")
        .order_by("-sold_at", "-id")
        .values_list("customer_id", flat=True)[:200]
    )
    for customer_id in rows:
        if customer_id not in seen:
            seen.append(customer_id)
        if len(seen) == limit:
            break
    return seen


def payments_received_by(organization: Organization, *, user_id: int, day: dt.date) -> list[CustomerPayment]:
    """The customer payments this person recorded for a day (voided ones left out), newest first."""
    return list(
        CustomerPayment.objects.for_organization(organization)
        .filter(created_by_id=user_id, received_on=day, voided_at__isnull=True)
        .select_related("customer")
        .order_by("-id")
    )


def owed_by_customer(organization: Organization) -> dict[int, Decimal]:
    """What each customer owes now (only those who owe something), from the receivables of D-062."""
    from . import receivables

    return {
        customer_id: balance.balance
        for customer_id, balance in receivables.customer_balances(organization).items()
        if balance.balance > 0
    }


# ---- The owner's dashboard (P7-T01, D-104) ----


@dataclass(frozen=True)
class OverdueCustomer:
    customer_id: int
    overdue: Decimal
    balance: Decimal


@dataclass(frozen=True)
class ReceivablesOverview:
    """What customers owe now (the customers who owe, as the ageing page counts it), the part past its due
    date, and the customers with something overdue, biggest first."""

    total: Decimal
    overdue: Decimal
    overdue_customers: tuple[OverdueCustomer, ...]


def receivables_overview(organization: Organization, *, today: dt.date | None = None) -> ReceivablesOverview:
    from . import receivables  # kept local to avoid a cycle with selectors (see outstanding_by_sale)

    zero = Decimal("0.000")
    balances = receivables.customer_balances(organization, today=today)
    owing = [value for value in balances.values() if value.balance > 0]
    late = sorted((value for value in owing if value.overdue > 0), key=lambda value: -value.overdue)
    return ReceivablesOverview(
        total=sum((value.balance for value in owing), zero),
        overdue=sum((value.overdue for value in owing), zero),
        overdue_customers=tuple(
            OverdueCustomer(customer_id=value.customer_id, overdue=value.overdue, balance=value.balance)
            for value in late
        ),
    )


def cash_collected(organization: Organization, *, date_from: dt.date, date_to: dt.date) -> Decimal:
    """Money received from customers from `date_from` to `date_to` (local days, inclusive): what they paid on the
    spot at a confirmed sale plus the payments they made later (voided ones left out). It is cash, not profit."""
    zero = Decimal("0.000")
    start = timezone.make_aware(dt.datetime.combine(date_from, dt.time.min))
    end = timezone.make_aware(dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time.min))
    on_the_spot = (
        Sale.objects.for_organization(organization)
        .filter(status=SaleStatus.CONFIRMED, sold_at__gte=start, sold_at__lt=end)
        .aggregate(total=Sum("amount_paid"))["total"]
    )
    later = (
        CustomerPayment.objects.for_organization(organization)
        .filter(voided_at__isnull=True, received_on__gte=date_from, received_on__lte=date_to)
        .aggregate(total=Sum("amount"))["total"]
    )
    return (on_the_spot or zero) + (later or zero)
