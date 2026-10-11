from django.urls import path

from . import views

urlpatterns = [
    # P2-T03 · quotes
    path("quotes", views.QuoteListView.as_view(), name="quote-list"),
    path("quotes/<int:quote_id>", views.QuoteDetailView.as_view(), name="quote-detail"),
    path("quotes/<int:quote_id>/send", views.QuoteSendView.as_view(), name="quote-send"),
    path("quotes/<int:quote_id>/accept", views.QuoteAcceptView.as_view(), name="quote-accept"),
    path("quotes/<int:quote_id>/refuse", views.QuoteRefuseView.as_view(), name="quote-refuse"),
]
