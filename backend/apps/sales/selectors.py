"""Reusable read queries of sales documents."""

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Case, CharField, Count, F, Prefetch, Q, QuerySet, Sum, Value, When
from django.utils import timezone

from apps.core.models import Organization

from .models import Quote, QuoteLine, QuoteStatus, Sale, SaleLine, SaleLineBatch, SaleStatus

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
) -> QuerySet[Sale]:
    """Sales newest first, each with `line_count`, its customer, place, quote and lines (product, batches).
    Days are those of `sold_at` in local time, both included; `search` matches the number and the
    customer's name or reference."""
    lines = (
        SaleLine.objects.select_related("product")
        .prefetch_related(Prefetch("batches", queryset=SaleLineBatch.objects.select_related("batch").order_by("id")))
        .order_by("id")
    )
    sales = (
        Sale.objects.for_organization(organization)
        .select_related("customer", "location", "quote", "created_by", "confirmed_by", "cancelled_by")
        .prefetch_related(Prefetch("lines", queryset=lines))
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
    if search := search.strip():
        sales = sales.filter(
            Q(number__icontains=search) | Q(customer__name__icontains=search) | Q(customer__reference__icontains=search)
        )
    return sales


def sale_of(organization: Organization, sale_id: int) -> Sale:
    """One sale with its lines and their batches. Raises Sale.DoesNotExist outside the organization."""
    return sales_of(organization).get(pk=sale_id)


def batch_sales(organization: Organization, *, batch_id: int) -> QuerySet[SaleLineBatch]:
    """What one lot (batch) sold, line by line, oldest sale first: confirmed sales only (a cancelled sale's
    kilos came back). Each row has its line (price, product) and sale (number, moment, customer, place)."""
    return (
        SaleLineBatch.objects.for_organization(organization)
        .filter(batch_id=batch_id, line__sale__status=SaleStatus.CONFIRMED)
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
    """Kg sold, revenue and cost of goods per lot (batch id), over confirmed sales: the sales side of a lot's
    result (D-040; Phase 6 adds the lot's own costs). Lots that sold nothing are left out."""
    rows = SaleLineBatch.objects.for_organization(organization).filter(line__sale__status=SaleStatus.CONFIRMED)
    if batch_ids is not None:
        rows = rows.filter(batch_id__in=list(batch_ids))
    totals = rows.values("batch_id").annotate(
        quantity=Sum("quantity"), revenue=Sum("revenue_amount"), cost=Sum("cost_amount")
    )
    return {
        row["batch_id"]: BatchSalesTotal(
            batch_id=row["batch_id"], quantity=row["quantity"], revenue=row["revenue"], cost=row["cost"]
        )
        for row in totals.order_by("batch_id")
    }
