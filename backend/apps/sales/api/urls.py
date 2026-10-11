from django.urls import path

from . import views

urlpatterns = [
    # P2-T03 · quotes
    path("quotes", views.QuoteListView.as_view(), name="quote-list"),
    path("quotes/<int:quote_id>", views.QuoteDetailView.as_view(), name="quote-detail"),
    path("quotes/<int:quote_id>/send", views.QuoteSendView.as_view(), name="quote-send"),
    path("quotes/<int:quote_id>/accept", views.QuoteAcceptView.as_view(), name="quote-accept"),
    path("quotes/<int:quote_id>/refuse", views.QuoteRefuseView.as_view(), name="quote-refuse"),
    # P2-T04 · sales
    path("quotes/<int:quote_id>/convert", views.QuoteConvertView.as_view(), name="quote-convert"),
    path("sales", views.SaleListView.as_view(), name="sale-list"),
    path("sales/<int:sale_id>", views.SaleDetailView.as_view(), name="sale-detail"),
    path("sales/<int:sale_id>/confirm", views.SaleConfirmView.as_view(), name="sale-confirm"),
    path("sales/<int:sale_id>/cancel", views.SaleCancelView.as_view(), name="sale-cancel"),
    path("batches/<int:batch_id>/sales", views.BatchSalesView.as_view(), name="batch-sales"),
]
