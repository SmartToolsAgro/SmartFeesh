from django.urls import path

from . import driver_views, views

urlpatterns = [
    path("receipts", views.ReceiptListView.as_view(), name="receipt-list"),
    path("receipts/differences", views.ReceiptDifferenceListView.as_view(), name="receipt-differences"),
    path("receipts/last-costs", views.LastCostListView.as_view(), name="receipt-last-costs"),
    path("receipts/<int:receipt_id>", views.ReceiptDetailView.as_view(), name="receipt-detail"),
    path("purchase-orders", views.OrderListView.as_view(), name="purchase-order-list"),
    path("purchase-orders/<int:order_id>", views.OrderDetailView.as_view(), name="purchase-order-detail"),
    path("purchase-orders/<int:order_id>/cancel", views.OrderCancelView.as_view(), name="purchase-order-cancel"),
    path("purchase-orders/<int:order_id>/close", views.OrderCloseView.as_view(), name="purchase-order-close"),
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
    path("field-purchases", views.FieldPurchaseListView.as_view(), name="field-purchase-list"),
    path("field-purchases/<int:purchase_id>", views.FieldPurchaseDetailView.as_view(), name="field-purchase-detail"),
    path("my-field-purchases", driver_views.MyFieldPurchasesView.as_view(), name="my-field-purchases"),
    path(
        "my-field-purchases/<int:purchase_id>",
        driver_views.MyFieldPurchaseView.as_view(),
        name="my-field-purchase",
    ),
    path("my-suppliers", driver_views.MySuppliersView.as_view(), name="my-suppliers"),
    path("my-purchase-costs", driver_views.MyPurchaseCostsView.as_view(), name="my-purchase-costs"),
    path(
        "field-purchases/<int:purchase_id>/refuse",
        views.FieldPurchaseRefuseView.as_view(),
        name="field-purchase-refuse",
    ),
]
