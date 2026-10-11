"""Reusable read queries of purchases."""

import datetime as dt
from decimal import Decimal

from django.db.models import Exists, F, OuterRef, Prefetch, Q, QuerySet

from apps.core.models import Organization

from .models import GoodsReceipt, GoodsReceiptLine

# A line differs when the accepted weight is not the invoiced one, or not the ordered one when there was an order.
DIFFERENT = ~Q(accepted_quantity=F("invoiced_quantity")) | (
    Q(ordered_quantity__isnull=False) & ~Q(accepted_quantity=F("ordered_quantity"))
)


def receipts_of(
    organization: Organization,
    *,
    supplier_id: int | None = None,
    search: str = "",
    with_differences: bool = False,
) -> QuerySet[GoodsReceipt]:
    """Receipts newest first, with supplier, location and lines (product and batch), and `has_differences`.

    `search` matches the receipt number, the supplier's reference and the supplier's name.
    """
    lines = GoodsReceiptLine.objects.select_related("product", "batch").order_by("id")
    receipts = (
        GoodsReceipt.objects.for_organization(organization)
        .select_related("supplier", "location", "created_by")
        .prefetch_related(Prefetch("lines", queryset=lines))
        .annotate(has_differences=Exists(GoodsReceiptLine.objects.filter(DIFFERENT, receipt=OuterRef("pk"))))
        .order_by("-received_on", "-id")
    )
    if supplier_id is not None:
        receipts = receipts.filter(supplier_id=supplier_id)
    if search := search.strip():
        receipts = receipts.filter(
            Q(number__icontains=search) | Q(supplier_reference__icontains=search) | Q(supplier__name__icontains=search)
        )
    if with_differences:
        receipts = receipts.filter(has_differences=True)
    return receipts


def receipt_of(organization: Organization, receipt_id: int) -> GoodsReceipt:
    """One receipt with its lines. Raises GoodsReceipt.DoesNotExist outside the organization."""
    return receipts_of(organization).get(pk=receipt_id)


def difference_lines(
    organization: Organization,
    *,
    supplier_id: int | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> QuerySet[GoodsReceiptLine]:
    """Receipt lines whose accepted weight differs from the invoiced or ordered weight, newest first."""
    lines = (
        GoodsReceiptLine.objects.for_organization(organization)
        .filter(DIFFERENT)
        .select_related("receipt", "receipt__supplier", "product", "batch")
        .order_by("-receipt__received_on", "-receipt_id", "id")
    )
    if supplier_id is not None:
        lines = lines.filter(receipt__supplier_id=supplier_id)
    if date_from is not None:
        lines = lines.filter(receipt__received_on__gte=date_from)
    if date_to is not None:
        lines = lines.filter(receipt__received_on__lte=date_to)
    return lines


def receipt_totals(receipt: GoodsReceipt) -> tuple[Decimal, Decimal]:
    """(invoiced total, accepted total): line amounts rounded to the millime, then added (ARCHITECTURE §4.1)."""
    lines = list(receipt.lines.all())
    invoiced = sum((line.invoiced_amount for line in lines), Decimal("0.000"))
    accepted = sum((line.accepted_amount for line in lines), Decimal("0.000"))
    return invoiced, accepted
