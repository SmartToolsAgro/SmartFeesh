from django.urls import path

from . import views

urlpatterns = [
    path("receipts", views.ReceiptListView.as_view(), name="receipt-list"),
    path("receipts/differences", views.ReceiptDifferenceListView.as_view(), name="receipt-differences"),
    path("receipts/last-costs", views.LastCostListView.as_view(), name="receipt-last-costs"),
    path("receipts/<int:receipt_id>", views.ReceiptDetailView.as_view(), name="receipt-detail"),
]
