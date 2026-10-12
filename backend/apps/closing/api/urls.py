from django.urls import path

from . import views

urlpatterns = [
    path("dashboard", views.DashboardView.as_view(), name="dashboard"),
    path("lots/<int:batch_id>/result", views.LotResultView.as_view(), name="lot-result"),
    path("lots/<int:batch_id>/close", views.CloseLotView.as_view(), name="lot-close"),
    path("lots/<int:batch_id>/reopen", views.ReopenLotView.as_view(), name="lot-reopen"),
    path("lots/<int:batch_id>/settlement", views.LotSettlementView.as_view(), name="lot-settlement"),
    path("lots/<int:batch_id>/settle", views.SettleLotView.as_view(), name="lot-settle"),
    path("lots/<int:batch_id>/late-adjustments", views.BookLateAdjustmentsView.as_view(), name="lot-late"),
    path("months", views.MonthListView.as_view(), name="month-list"),
    path("months/<str:month>", views.MonthView.as_view(), name="month-detail"),
    path("months/<str:month>/review", views.ReviewMonthView.as_view(), name="month-review"),
    path("months/<str:month>/approve", views.ApproveMonthView.as_view(), name="month-approve"),
    path("months/<str:month>/reopen", views.ReopenMonthView.as_view(), name="month-reopen"),
    path("partners/<int:partner_id>/balances", views.PartnerBalancesView.as_view(), name="partner-balances"),
]
