"""Reusable read queries of purchases."""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal

from django.db.models import (
    DecimalField,
    Exists,
    ExpressionWrapper,
    F,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core.documents import DocumentFilters, DocumentRow, Tone, document_key
from apps.core.models import Organization

from .models import (
    RECEIVABLE_ORDER_STATUSES,
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    SupplierInvoice,
    SupplierInvoiceReceipt,
    SupplierInvoiceStatus,
    SupplierPayment,
    SupplierPaymentAllocation,
)

if TYPE_CHECKING:
    from .statements import SupplierStatement

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
    uninvoiced: bool = False,
    purchase_order_id: int | None = None,
) -> QuerySet[GoodsReceipt]:
    """Receipts newest first, with supplier, location, lines (product and batch), their invoice if any,
    and `has_differences`.

    `search` matches the receipt number, the supplier's reference and the supplier's name. `uninvoiced`
    keeps the receipts not on any supplier invoice yet, draft or posted.
    """
    lines = GoodsReceiptLine.objects.select_related("product", "batch").order_by("id")
    receipts = (
        GoodsReceipt.objects.for_organization(organization)
        .select_related("supplier", "location", "created_by", "invoice_link__invoice", "purchase_order")
        .prefetch_related(Prefetch("lines", queryset=lines))
        .annotate(has_differences=Exists(GoodsReceiptLine.objects.filter(DIFFERENT, receipt=OuterRef("pk"))))
        .order_by("-received_on", "-id")
    )
    if supplier_id is not None:
        receipts = receipts.filter(supplier_id=supplier_id)
    if purchase_order_id is not None:
        receipts = receipts.filter(purchase_order_id=purchase_order_id)
    if search := search.strip():
        receipts = receipts.filter(
            Q(number__icontains=search) | Q(supplier_reference__icontains=search) | Q(supplier__name__icontains=search)
        )
    if with_differences:
        receipts = receipts.filter(has_differences=True)
    if uninvoiced:
        receipts = receipts.filter(invoice_link__isnull=True)
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


ZERO = Decimal("0.000")


# ---- Purchase orders (D-076) ----

type OrderStatusFilter = Literal["open", "partly_received", "received", "closed", "cancelled", "pending"]


def orders_of(
    organization: Organization,
    *,
    supplier_id: int | None = None,
    status: OrderStatusFilter | None = None,
    search: str = "",
) -> QuerySet[PurchaseOrder]:
    """Purchase orders newest first, with supplier, receipts and lines carrying `received_quantity`.

    `status="pending"` keeps the orders still waiting for goods (open or partly received). `search`
    matches the order number and the supplier's name.
    """
    lines = (
        PurchaseOrderLine.objects.select_related("product")
        .annotate(received_quantity=Coalesce(Sum("receipt_lines__accepted_quantity"), ZERO, output_field=QUANTITY))
        .order_by("id")
    )
    receipts = GoodsReceipt.objects.order_by("received_on", "id")
    orders = (
        PurchaseOrder.objects.for_organization(organization)
        .select_related("supplier", "created_by")
        .prefetch_related(Prefetch("lines", queryset=lines))
        .prefetch_related(Prefetch("receipts", queryset=receipts))
        .order_by("-ordered_on", "-id")
    )
    if supplier_id is not None:
        orders = orders.filter(supplier_id=supplier_id)
    if status == "pending":
        orders = orders.filter(status__in=RECEIVABLE_ORDER_STATUSES)
    elif status is not None:
        orders = orders.filter(status=status)
    if search := search.strip():
        orders = orders.filter(Q(number__icontains=search) | Q(supplier__name__icontains=search))
    return orders


def order_of(organization: Organization, order_id: int) -> PurchaseOrder:
    """One order with its lines and receipts. Raises PurchaseOrder.DoesNotExist outside the organization."""
    return orders_of(organization).get(pk=order_id)


def order_line_remaining(line: PurchaseOrderLine) -> Decimal:
    """Weight still to come on a line (never negative: a delivery of more than asked leaves nothing)."""
    return max(line.ordered_quantity - getattr(line, "received_quantity", ZERO), ZERO)


# ---- Supplier invoices, payments and balances (P1-T08, D-043) ----
AMOUNT = DecimalField(max_digits=14, decimal_places=3)
QUANTITY = DecimalField(max_digits=12, decimal_places=3)
# Posted and not fully paid: what is still owed on invoices.
OPEN_STATUSES = (SupplierInvoiceStatus.POSTED, SupplierInvoiceStatus.PARTLY_PAID)

type InvoiceStatusFilter = Literal["draft", "posted", "partly_paid", "paid", "open"]


def _sum_of_allocations(**match: Any) -> Coalesce:
    """The sum of the allocations matching `match` (an OuterRef), as a subquery: no join, no duplicate rows."""
    group = next(iter(match))
    allocations = (
        SupplierPaymentAllocation.objects.filter(**match)
        .order_by()
        .values(group)
        .annotate(total=Sum("amount"))
        .values("total")
    )
    return Coalesce(Subquery(allocations, output_field=AMOUNT), Value(ZERO), output_field=AMOUNT)


def invoices_of(
    organization: Organization,
    *,
    supplier_id: int | None = None,
    status: InvoiceStatusFilter | None = None,
    search: str = "",
    overdue: bool = False,
) -> QuerySet[SupplierInvoice]:
    """Supplier invoices newest first, with their receipts and allocations, `paid_amount` and `outstanding`.

    `status="open"` keeps the posted invoices not fully paid; `overdue` keeps those whose due date has
    passed. `search` matches our number, the supplier's invoice number and the supplier's name.
    """
    links = SupplierInvoiceReceipt.objects.select_related("receipt").order_by("receipt__received_on", "receipt_id")
    allocations = SupplierPaymentAllocation.objects.select_related("payment").order_by("payment__paid_on", "id")
    invoices = (
        SupplierInvoice.objects.for_organization(organization)
        .select_related("supplier", "created_by", "posted_by")
        .prefetch_related(Prefetch("receipt_links", queryset=links))
        .prefetch_related(Prefetch("allocations", queryset=allocations))
        .annotate(paid_amount=_sum_of_allocations(invoice=OuterRef("pk")))
        .annotate(outstanding=ExpressionWrapper(F("total") - F("paid_amount"), output_field=AMOUNT))
        .order_by("-invoice_date", "-id")
    )
    if supplier_id is not None:
        invoices = invoices.filter(supplier_id=supplier_id)
    if status == "open":
        invoices = invoices.filter(status__in=OPEN_STATUSES)
    elif status is not None:
        invoices = invoices.filter(status=status)
    if overdue:
        invoices = invoices.filter(status__in=OPEN_STATUSES, due_date__lt=timezone.localdate())
    if search := search.strip():
        invoices = invoices.filter(
            Q(number__icontains=search) | Q(supplier_reference__icontains=search) | Q(supplier__name__icontains=search)
        )
    return invoices


def invoice_of(organization: Organization, invoice_id: int) -> SupplierInvoice:
    """One invoice with its receipts and payments. Raises SupplierInvoice.DoesNotExist outside the organization."""
    return invoices_of(organization).get(pk=invoice_id)


def open_invoices_of(organization: Organization, *, supplier_id: int) -> QuerySet[SupplierInvoice]:
    """A supplier's posted invoices still to pay, the oldest due date first: the order a payment settles them."""
    return invoices_of(organization, supplier_id=supplier_id, status="open").order_by("due_date", "invoice_date", "id")


def payments_of(
    organization: Organization, *, supplier_id: int | None = None, search: str = "", unallocated: bool = False
) -> QuerySet[SupplierPayment]:
    """Supplier payments newest first, with their allocations, `allocated_amount` and `unallocated_amount`.

    `unallocated` keeps the payments with a part not allocated to an invoice yet (advances).
    `search` matches our number, the cheque or transfer reference and the supplier's name.
    """
    allocations = SupplierPaymentAllocation.objects.select_related("invoice").order_by("id")
    payments = (
        SupplierPayment.objects.for_organization(organization)
        .select_related("supplier", "created_by")
        .prefetch_related(Prefetch("allocations", queryset=allocations))
        .annotate(allocated_amount=_sum_of_allocations(payment=OuterRef("pk")))
        .annotate(unallocated_amount=ExpressionWrapper(F("amount") - F("allocated_amount"), output_field=AMOUNT))
        .order_by("-paid_on", "-id")
    )
    if supplier_id is not None:
        payments = payments.filter(supplier_id=supplier_id)
    if unallocated:
        payments = payments.filter(unallocated_amount__gt=0)
    if search := search.strip():
        payments = payments.filter(
            Q(number__icontains=search) | Q(reference__icontains=search) | Q(supplier__name__icontains=search)
        )
    return payments


def payment_of(organization: Organization, payment_id: int) -> SupplierPayment:
    """One payment with its allocations. Raises SupplierPayment.DoesNotExist outside the organization."""
    return payments_of(organization).get(pk=payment_id)


@dataclass(frozen=True)
class SupplierBalance:
    """What the company owes one supplier for goods: the trade payable only (D-040, D-043).

    `balance` = posted invoices − payments. Negative, the supplier holds an advance. A partner's capital
    and profit share are other balances (Phase 6) and never appear here.
    """

    supplier_id: int
    invoiced: Decimal  # posted invoices, paid or not
    paid: Decimal  # every payment, allocated or not
    balance: Decimal
    outstanding: Decimal  # still to pay on posted invoices
    unallocated: Decimal  # paid but not allocated to an invoice yet (advances)
    overdue: Decimal  # still to pay on invoices past their due date
    open_invoices: int
    overdue_invoices: int
    draft_invoices: int
    draft_total: Decimal
    uninvoiced_receipts: int  # received but on no invoice yet: not owed until invoiced
    uninvoiced_total: Decimal


def _total(queryset: QuerySet[Any], field: str) -> Decimal:
    value = queryset.aggregate(total=Sum(field))["total"]
    return value if value is not None else ZERO


# ---- The "Documents" page (P2-T11, D-102) ----

_ORDER_TONES: dict[str, Tone] = {
    PurchaseOrderStatus.OPEN: "waiting",
    PurchaseOrderStatus.PARTLY_RECEIVED: "waiting",
    PurchaseOrderStatus.RECEIVED: "done",
    PurchaseOrderStatus.CLOSED: "done",
    PurchaseOrderStatus.CANCELLED: "cancelled",
}


def _in_days(queryset: QuerySet[Any], field: str, filters: DocumentFilters) -> QuerySet[Any]:
    if filters.date_from is not None:
        queryset = queryset.filter(**{f"{field}__gte": filters.date_from})
    if filters.date_to is not None:
        queryset = queryset.filter(**{f"{field}__lte": filters.date_to})
    if search := filters.search.strip():
        queryset = queryset.filter(Q(number__icontains=search) | Q(supplier__name__icontains=search))
    return queryset


def document_rows(organization: Organization, filters: DocumentFilters, *, may_write: bool) -> list[DocumentRow]:
    """Purchase orders (BA), goods receipts (BR) and supplier invoices (FF) as rows of the "Documents" page.

    `may_write` is whether the person may change purchases (owner or manager); `actions` follow the services'
    rules, which still check everything when an action runs.
    """
    rows: list[DocumentRow] = []
    wanted = filters.types

    if not wanted or "BA" in wanted:
        lines = PurchaseOrderLine.objects.order_by("id")
        orders = (
            PurchaseOrder.objects.for_organization(organization)
            .select_related("supplier")
            .prefetch_related(Prefetch("lines", queryset=lines))
            .annotate(has_receipts=Exists(GoodsReceipt.objects.filter(purchase_order=OuterRef("pk"))))
        )
        for order in _in_days(orders, "ordered_on", filters):
            status = PurchaseOrderStatus(order.status)
            actions: list[str] = []
            if may_write and status in RECEIVABLE_ORDER_STATUSES:
                actions.append("receive")
                if status == PurchaseOrderStatus.OPEN and not order.has_receipts:
                    actions.append("cancel")
                if status == PurchaseOrderStatus.PARTLY_RECEIVED:
                    actions.append("close")
            rows.append(
                DocumentRow(
                    type="BA",
                    id=order.pk,
                    number=order.number,
                    partner_side="supplier",
                    partner_id=order.supplier_id,
                    partner_name=order.supplier.name,
                    date=order.ordered_on,
                    amount=sum((line.ordered_amount for line in order.lines.all()), ZERO),
                    status=status.value,
                    status_label=str(status.label),
                    tone=_ORDER_TONES[status],
                    actions=actions,
                )
            )

    if not wanted or "BR" in wanted:
        receipt_lines = GoodsReceiptLine.objects.order_by("id")
        receipts = (
            GoodsReceipt.objects.for_organization(organization)
            .select_related("supplier")
            .prefetch_related(Prefetch("lines", queryset=receipt_lines))
            .annotate(invoiced=Exists(SupplierInvoiceReceipt.objects.filter(receipt=OuterRef("pk"))))
        )
        for receipt in _in_days(receipts, "received_on", filters):
            rows.append(
                DocumentRow(
                    type="BR",
                    id=receipt.pk,
                    number=receipt.number,
                    partner_side="supplier",
                    partner_id=receipt.supplier_id,
                    partner_name=receipt.supplier.name,
                    date=receipt.received_on,
                    # What the supplier charges for it (invoiced kg × cost, D-039).
                    amount=receipt_totals(receipt)[0],
                    # A receipt has no status: the goods are in stock once it is saved.
                    status="received",
                    status_label=str(_("Reçu")),
                    tone="done",
                    parents=[document_key("BA", receipt.purchase_order_id)] if receipt.purchase_order_id else [],
                    actions=["to_supplier_invoice"] if may_write and not receipt.invoiced else [],
                )
            )

    if not wanted or "FF" in wanted:
        links = SupplierInvoiceReceipt.objects.order_by("receipt__received_on", "receipt_id")
        invoices = (
            SupplierInvoice.objects.for_organization(organization)
            .select_related("supplier")
            .prefetch_related(Prefetch("receipt_links", queryset=links))
        )
        for invoice in _in_days(invoices, "invoice_date", filters):
            invoice_status = SupplierInvoiceStatus(invoice.status)
            actions = []
            if may_write:
                if invoice_status == SupplierInvoiceStatus.DRAFT:
                    actions = ["edit", "post", "delete"]
                elif invoice_status in OPEN_STATUSES:
                    actions = ["pay"]
            rows.append(
                DocumentRow(
                    type="FF",
                    id=invoice.pk,
                    number=invoice.number,
                    partner_side="supplier",
                    partner_id=invoice.supplier_id,
                    partner_name=invoice.supplier.name,
                    date=invoice.invoice_date,
                    amount=invoice.total,
                    status=invoice_status.value,
                    status_label=str(invoice_status.label),
                    tone="draft" if invoice_status == SupplierInvoiceStatus.DRAFT else "done",
                    parents=[document_key("BR", link.receipt_id) for link in invoice.receipt_links.all()],
                    actions=actions,
                )
            )
    return rows


def supplier_balance(organization: Organization, supplier_id: int) -> SupplierBalance:
    """The trade balance of one supplier of the organization (an unknown supplier simply has zeros)."""
    invoices = SupplierInvoice.objects.for_organization(organization).filter(supplier_id=supplier_id)
    posted = invoices.exclude(status=SupplierInvoiceStatus.DRAFT)
    drafts = invoices.filter(status=SupplierInvoiceStatus.DRAFT)
    payments = SupplierPayment.objects.for_organization(organization).filter(supplier_id=supplier_id)
    allocations = SupplierPaymentAllocation.objects.for_organization(organization).filter(
        payment__supplier_id=supplier_id
    )
    open_invoices = list(invoices_of(organization, supplier_id=supplier_id, status="open"))
    today = timezone.localdate()
    late = [invoice for invoice in open_invoices if invoice.due_date < today]
    uninvoiced = list(receipts_of(organization, supplier_id=supplier_id, uninvoiced=True))
    invoiced = _total(posted, "total")
    paid = _total(payments, "amount")
    return SupplierBalance(
        supplier_id=supplier_id,
        invoiced=invoiced,
        paid=paid,
        balance=invoiced - paid,
        outstanding=sum((getattr(invoice, "outstanding") for invoice in open_invoices), ZERO),  # noqa: B009
        unallocated=paid - _total(allocations, "amount"),
        overdue=sum((getattr(invoice, "outstanding") for invoice in late), ZERO),  # noqa: B009
        open_invoices=len(open_invoices),
        overdue_invoices=len(late),
        draft_invoices=drafts.count(),
        draft_total=_total(drafts, "total"),
        uninvoiced_receipts=len(uninvoiced),
        uninvoiced_total=sum((receipt_totals(receipt)[0] for receipt in uninvoiced), ZERO),
    )


def payments_by_day(organization: Organization, *, date_from: dt.date, date_to: dt.date) -> dict[dt.date, Decimal]:
    """Money paid to suppliers per day (`paid_on`), inclusive."""
    rows = (
        SupplierPayment.objects.for_organization(organization)
        .filter(paid_on__gte=date_from, paid_on__lte=date_to)
        .values("paid_on")
        .annotate(total=Sum("amount"))
    )
    return {row["paid_on"]: row["total"] for row in rows}


def supplier_statement(
    organization: Organization, supplier_id: int, *, date_from: dt.date | None, date_to: dt.date
) -> "SupplierStatement":
    """One supplier's receipts (line by line), invoices, payments and trade account from `date_from` (the beginning
    when None) to `date_to` (`statements.SupplierStatement`, D-156)."""
    from . import statements

    return statements.supplier_statement(organization, supplier_id, date_from=date_from, date_to=date_to)
