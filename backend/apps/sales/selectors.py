"""Reusable read queries of sales documents."""

import datetime as dt

from django.db.models import Case, CharField, Count, F, Prefetch, Q, QuerySet, Value, When
from django.utils import timezone

from apps.core.models import Organization

from .models import Quote, QuoteLine, QuoteStatus

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
