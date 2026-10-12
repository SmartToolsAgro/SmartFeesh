from django.urls import path

from . import views

urlpatterns = [
    path("reports/sales", views.SalesReportView.as_view(), name="report-sales"),
    path("reports/sales/export", views.SalesReportExportView.as_view(), name="report-sales-export"),
    path("reports/stock-value", views.StockValueReportView.as_view(), name="report-stock-value"),
    path("reports/stock-value/export", views.StockValueExportView.as_view(), name="report-stock-value-export"),
    path("reports/slow-moving", views.SlowMovingReportView.as_view(), name="report-slow-moving"),
    path("reports/slow-moving/export", views.SlowMovingExportView.as_view(), name="report-slow-moving-export"),
    path("reports/losses", views.LossesReportView.as_view(), name="report-losses"),
    path("reports/losses/export", views.LossesReportExportView.as_view(), name="report-losses-export"),
]
