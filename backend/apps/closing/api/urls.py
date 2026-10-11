from django.urls import path

from . import views

urlpatterns = [
    path("lots/<int:batch_id>/result", views.LotResultView.as_view(), name="lot-result"),
    path("lots/<int:batch_id>/close", views.CloseLotView.as_view(), name="lot-close"),
    path("lots/<int:batch_id>/reopen", views.ReopenLotView.as_view(), name="lot-reopen"),
    path("lots/<int:batch_id>/settlement", views.LotSettlementView.as_view(), name="lot-settlement"),
    path("lots/<int:batch_id>/settle", views.SettleLotView.as_view(), name="lot-settle"),
    path("lots/<int:batch_id>/late-adjustments", views.BookLateAdjustmentsView.as_view(), name="lot-late"),
    path("partners/<int:partner_id>/balances", views.PartnerBalancesView.as_view(), name="partner-balances"),
]
