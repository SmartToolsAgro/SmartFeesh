from django.urls import path

from . import financial_views as fin
from . import statement_views, views

urlpatterns = [
    path("reports/sales", views.SalesReportView.as_view(), name="report-sales"),
    path("reports/sales/export", views.SalesReportExportView.as_view(), name="report-sales-export"),
    path("reports/stock-value", views.StockValueReportView.as_view(), name="report-stock-value"),
    path("reports/stock-value/export", views.StockValueExportView.as_view(), name="report-stock-value-export"),
    path("reports/slow-moving", views.SlowMovingReportView.as_view(), name="report-slow-moving"),
    path("reports/slow-moving/export", views.SlowMovingExportView.as_view(), name="report-slow-moving-export"),
    path("reports/losses", views.LossesReportView.as_view(), name="report-losses"),
    path("reports/losses/export", views.LossesReportExportView.as_view(), name="report-losses-export"),
    # P7-T04 · financial reports (owner and accountant)
    path("reports/month-result", fin.MonthResultView.as_view(), name="report-month-result"),
    path("reports/month-result/export", fin.MonthResultExportView.as_view(), name="report-month-result-export"),
    path("reports/cash-flow", fin.CashFlowView.as_view(), name="report-cash-flow"),
    path("reports/cash-flow/export", fin.CashFlowExportView.as_view(), name="report-cash-flow-export"),
    path("reports/customer-balances", fin.CustomerBalancesView.as_view(), name="report-customer-balances"),
    path(
        "reports/customer-balances/export",
        fin.CustomerBalancesExportView.as_view(),
        name="report-customer-balances-export",
    ),
    path("reports/supplier-balances", fin.SupplierBalancesView.as_view(), name="report-supplier-balances"),
    path(
        "reports/supplier-balances/export",
        fin.SupplierBalancesExportView.as_view(),
        name="report-supplier-balances-export",
    ),
    path("reports/unpaid-salaries", fin.UnpaidSalariesView.as_view(), name="report-unpaid-salaries"),
    path(
        "reports/unpaid-salaries/export",
        fin.UnpaidSalariesExportView.as_view(),
        name="report-unpaid-salaries-export",
    ),
    path("reports/partners", fin.PartnerReportView.as_view(), name="report-partners"),
    path("reports/partners/export", fin.PartnerReportExportView.as_view(), name="report-partners-export"),
    # Statements of one customer or supplier over chosen dates (D-156)
    path(
        "reports/customer-statement/<int:customer_id>/pdf",
        statement_views.CustomerStatementPdfView.as_view(),
        name="report-customer-statement",
    ),
    path(
        "reports/supplier-statement/<int:supplier_id>/pdf",
        statement_views.SupplierStatementPdfView.as_view(),
        name="report-supplier-statement",
    ),
]
