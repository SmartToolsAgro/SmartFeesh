from typing import Any

from django.contrib import admin
from django.db.models import Model
from django.http import HttpRequest

from .models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    SupplierInvoice,
    SupplierInvoiceReceipt,
    SupplierPayment,
    SupplierPaymentAllocation,
)


class ReadOnlyAdmin[T: Model](admin.ModelAdmin[T]):
    """For looking only: invoices and payments are recorded through the services, which check and audit them."""

    def has_add_permission(self, request: HttpRequest, *args: Any) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


class LineInline(admin.TabularInline[GoodsReceiptLine, GoodsReceipt]):
    model = GoodsReceiptLine
    fields = ("product", "batch", "ordered_quantity", "invoiced_quantity", "accepted_quantity", "unit_cost")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin[GoodsReceipt]):
    """For looking only: receipts are recorded through the services, which create batches and stock."""

    list_display = ("number", "received_on", "supplier", "location", "supplier_reference", "organization")
    list_filter = ("organization", "received_on")
    search_fields = ("number", "supplier_reference")
    list_select_related = ("supplier", "location", "organization")
    inlines = (LineInline,)

    def has_add_permission(self, request: HttpRequest, *args: Any) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


class OrderLineInline(admin.TabularInline[PurchaseOrderLine, PurchaseOrder]):
    model = PurchaseOrderLine
    fields = ("product", "ordered_quantity", "unit_cost")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(ReadOnlyAdmin[PurchaseOrder]):
    list_display = ("number", "ordered_on", "expected_on", "supplier", "status", "organization")
    list_filter = ("organization", "status", "ordered_on")
    search_fields = ("number",)
    list_select_related = ("supplier", "organization")
    inlines = (OrderLineInline,)


class InvoiceReceiptInline(admin.TabularInline[SupplierInvoiceReceipt, SupplierInvoice]):
    model = SupplierInvoiceReceipt
    fields = ("receipt", "amount")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(SupplierInvoice)
class SupplierInvoiceAdmin(ReadOnlyAdmin[SupplierInvoice]):
    list_display = ("number", "invoice_date", "due_date", "supplier", "status", "total", "organization")
    list_filter = ("organization", "status", "invoice_date")
    search_fields = ("number", "supplier_reference")
    list_select_related = ("supplier", "organization")
    inlines = (InvoiceReceiptInline,)


class AllocationInline(admin.TabularInline[SupplierPaymentAllocation, SupplierPayment]):
    model = SupplierPaymentAllocation
    fields = ("invoice", "amount", "created_at")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(SupplierPayment)
class SupplierPaymentAdmin(ReadOnlyAdmin[SupplierPayment]):
    list_display = ("number", "paid_on", "supplier", "method", "amount", "reference", "organization")
    list_filter = ("organization", "method", "paid_on")
    search_fields = ("number", "reference")
    list_select_related = ("supplier", "organization")
    inlines = (AllocationInline,)
