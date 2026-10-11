from django.urls import path

from . import views

urlpatterns = [
    path("receipts", views.ReceiptListView.as_view(), name="receipt-list"),
    path("receipts/differences", views.ReceiptDifferenceListView.as_view(), name="receipt-differences"),
    path("receipts/last-costs", views.LastCostListView.as_view(), name="receipt-last-costs"),
    path("receipts/<int:receipt_id>", views.ReceiptDetailView.as_view(), name="receipt-detail"),
    path("supplier-invoices", views.SupplierInvoiceListView.as_view(), name="supplier-invoice-list"),
    path(
        "supplier-invoices/<int:invoice_id>", views.SupplierInvoiceDetailView.as_view(), name="supplier-invoice-detail"
    ),
    path(
        "supplier-invoices/<int:invoice_id>/post", views.SupplierInvoicePostView.as_view(), name="supplier-invoice-post"
    ),
    path("supplier-payments", views.SupplierPaymentListView.as_view(), name="supplier-payment-list"),
    path(
        "supplier-payments/<int:payment_id>", views.SupplierPaymentDetailView.as_view(), name="supplier-payment-detail"
    ),
    path(
        "supplier-payments/<int:payment_id>/allocations",
        views.SupplierPaymentAllocateView.as_view(),
        name="supplier-payment-allocate",
    ),
    path("supplier-balances/<int:supplier_id>", views.SupplierBalanceView.as_view(), name="supplier-balance"),
]
