"""Financial reports (P7-T04, D-116): the owner's and the accountant's figures, never the manager's or a driver's."""

from typing import Any

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer

from apps.core.models import Role
from apps.reports import exports, financial, partners

from .financial_serializers import (
    CashFlowSerializer,
    CashQuerySerializer,
    CustomerBalancesSerializer,
    MonthQuerySerializer,
    MonthResultSerializer,
    PartnerReportSerializer,
    SupplierBalancesSerializer,
    UnpaidSalariesSerializer,
)
from .serializers import PeriodQuerySerializer
from .views import ReadsReports, ReportView, _xlsx

MONTH_PARAMS = [OpenApiParameter("month", OpenApiTypes.DATE, description="Any day of the month (default: now).")]
CASH_PARAMS = [
    OpenApiParameter("group_by", str, enum=list(financial.CASH_GROUPS)),
    OpenApiParameter("date_from", OpenApiTypes.DATE, description="First day (default: first of this month)."),
    OpenApiParameter("date_to", OpenApiTypes.DATE, description="Last day, inclusive (default: today)."),
]


class ReadsFinancialReports(ReadsReports):
    """The company's money: the owner and the accountant."""

    roles = frozenset({Role.OWNER, Role.ACCOUNTANT})


class FinancialView(ReportView):
    permission_classes = (ReadsFinancialReports,)
    query_serializer: type[Serializer[Any]] = PeriodQuerySerializer


# ---- Month result ----


class MonthResultView(FinancialView):
    query_serializer = MonthQuerySerializer

    @extend_schema(operation_id="getMonthResultReport", parameters=MONTH_PARAMS, responses=MonthResultSerializer)
    def get(self, request: Request) -> Response:
        """The month's result exactly as the monthly closing computes it (sales, cost of goods, spoilage, expenses
        by category, personnel, net result)."""
        result = financial.month_result(self.organization, month=self.query(request)["month"])
        return Response(MonthResultSerializer(result).data)


class MonthResultExportView(FinancialView):
    query_serializer = MonthQuerySerializer

    @extend_schema(operation_id="exportMonthResultReport", parameters=MONTH_PARAMS, responses=OpenApiTypes.BINARY)
    def get(self, request: Request) -> HttpResponse:
        """The month's result and its expenses by category as an Excel file."""
        result = financial.month_result(self.organization, month=self.query(request)["month"])
        rows: list[list[Any]] = [
            ["Chiffre d'affaires HT", result.revenue],
            ["Coût des marchandises vendues", result.cogs],
            ["Marge brute", result.gross_margin],
            ["Pertes de marchandise", result.spoilage],
            ["Charges", result.expenses_total],
            ["Personnel", result.personnel],
            ["Résultat net", result.net_result],
            ["", ""],
            *[[f"Charges : {c.name} ({c.count})", c.total] for c in result.categories],
        ]
        content = exports.workbook_bytes(title="Résultat du mois", headers=["Libellé", "Montant"], rows=rows)
        return _xlsx(f"resultat-{result.month:%Y-%m}", content)


# ---- Cash flow ----


class CashFlowView(FinancialView):
    query_serializer = CashQuerySerializer

    def report(self, request: Request) -> financial.CashFlow:
        query = self.query(request)
        return financial.cash_flow(
            self.organization, date_from=query["date_from"], date_to=query["date_to"], group_by=query["group_by"]
        )

    @extend_schema(operation_id="getCashFlowReport", parameters=CASH_PARAMS, responses=CashFlowSerializer)
    def get(self, request: Request) -> Response:
        """Money in (paid at sales, customer payments) against money out (supplier payments, salaries paid, approved
        expenses) by day, week or month."""
        return Response(CashFlowSerializer(self.report(request)).data)


class CashFlowExportView(CashFlowView):
    @extend_schema(operation_id="exportCashFlowReport", parameters=CASH_PARAMS, responses=OpenApiTypes.BINARY)
    def get(self, request: Request) -> HttpResponse:  # type: ignore[override]
        """The cash flow as an Excel file."""
        report = self.report(request)
        content = exports.workbook_bytes(
            title="Trésorerie",
            headers=["Période", "Encaissements", "Décaissements", "Solde"],
            rows=[[r.key, r.cash_in, r.cash_out, r.net] for r in report.rows],
            totals=["Total", report.total_in, report.total_out, report.net],
        )
        return _xlsx(f"tresorerie-{report.date_from}-{report.date_to}", content)


# ---- Customers, suppliers, salaries ----


class CustomerBalancesView(FinancialView):
    @extend_schema(operation_id="getCustomerBalancesReport", responses=CustomerBalancesSerializer)
    def get(self, request: Request) -> Response:
        """Customers who owe, biggest first, with the part overdue and the ageing (0-30, 31-60, 61+ days)."""
        return Response(CustomerBalancesSerializer(financial.customer_balances(self.organization)).data)


class CustomerBalancesExportView(FinancialView):
    @extend_schema(operation_id="exportCustomerBalancesReport", responses=OpenApiTypes.BINARY)
    def get(self, request: Request) -> HttpResponse:
        """What customers owe, as an Excel file."""
        report = financial.customer_balances(self.organization)
        content = exports.workbook_bytes(
            title="Créances clients",
            headers=["Client", "Solde dû", "En retard", "0-30 jours", "31-60 jours", "61 jours et +"],
            rows=[[r.name, r.balance, r.overdue, r.d0_30, r.d31_60, r.d60_plus] for r in report.rows],
            totals=["Total", report.total_balance, report.total_overdue, report.d0_30, report.d31_60, report.d60_plus],
        )
        return _xlsx("creances-clients", content)


class SupplierBalancesView(FinancialView):
    @extend_schema(operation_id="getSupplierBalancesReport", responses=SupplierBalancesSerializer)
    def get(self, request: Request) -> Response:
        """What the company owes suppliers for goods (invoices minus payments), with what is overdue and what is
        received but not invoiced yet."""
        return Response(SupplierBalancesSerializer(financial.supplier_balances(self.organization)).data)


class SupplierBalancesExportView(FinancialView):
    @extend_schema(operation_id="exportSupplierBalancesReport", responses=OpenApiTypes.BINARY)
    def get(self, request: Request) -> HttpResponse:
        """What is owed to suppliers, as an Excel file."""
        report = financial.supplier_balances(self.organization)
        content = exports.workbook_bytes(
            title="Dettes fournisseurs",
            headers=["Fournisseur", "Facturé", "Payé", "Solde dû", "En retard", "Reçu non facturé"],
            rows=[[r.name, r.invoiced, r.paid, r.balance, r.overdue, r.uninvoiced] for r in report.rows],
            totals=["Total", "", "", report.total_balance, report.total_overdue, report.total_uninvoiced],
        )
        return _xlsx("dettes-fournisseurs", content)


class UnpaidSalariesView(FinancialView):
    @extend_schema(operation_id="getUnpaidSalariesReport", responses=UnpaidSalariesSerializer)
    def get(self, request: Request) -> Response:
        """What is still to pay on approved salaries, per employee."""
        return Response(UnpaidSalariesSerializer(financial.unpaid_salaries(self.organization)).data)


class UnpaidSalariesExportView(FinancialView):
    @extend_schema(operation_id="exportUnpaidSalariesReport", responses=OpenApiTypes.BINARY)
    def get(self, request: Request) -> HttpResponse:
        """Unpaid salaries as an Excel file."""
        report = financial.unpaid_salaries(self.organization)
        content = exports.workbook_bytes(
            title="Salaires à payer",
            headers=["Employé", "Reste à payer"],
            rows=[[r.name, r.unpaid] for r in report.rows],
            totals=["Total", report.total],
        )
        return _xlsx("salaires-a-payer", content)


# ---- Partners (P7-T05, D-117) ----

PERIOD_PARAMS = [
    OpenApiParameter("date_from", OpenApiTypes.DATE, description="First day (default: first of this month)."),
    OpenApiParameter("date_to", OpenApiTypes.DATE, description="Last day, inclusive (default: today)."),
]


class PartnerReportView(FinancialView):
    query_serializer = PeriodQuerySerializer

    def report(self, request: Request) -> partners.PartnerReport:
        query = self.query(request)
        return partners.partner_report(self.organization, date_from=query["date_from"], date_to=query["date_to"])

    @extend_schema(operation_id="getPartnerReport", parameters=PERIOD_PARAMS, responses=PartnerReportSerializer)
    def get(self, request: Request) -> Response:
        """Per partner over a period: capital put in, loss share taken from it and capital returned, the capital
        still in the company now; profit share earned, uncovered losses, late adjustments and paid, and the share
        still due now. The balances are those of the partner screens."""
        return Response(PartnerReportSerializer(self.report(request)).data)


class PartnerReportExportView(PartnerReportView):
    @extend_schema(operation_id="exportPartnerReport", parameters=PERIOD_PARAMS, responses=OpenApiTypes.BINARY)
    def get(self, request: Request) -> HttpResponse:  # type: ignore[override]
        """The partner report as an Excel file."""
        report = self.report(request)
        totals = report.totals
        content = exports.workbook_bytes(
            title="Partenaires",
            headers=[
                "Partenaire",
                "Lots",
                "Apports",
                "Perte déduite du capital",
                "Capital rendu",
                "Capital encore engagé",
                "Parts de bénéfice",
                "Pertes non couvertes",
                "Régularisations",
                "Parts payées",
                "Part encore due",
            ],
            rows=[
                [
                    r.name,
                    r.lots,
                    r.contributed,
                    r.loss_deducted,
                    r.returned,
                    r.capital_outstanding,
                    r.share,
                    r.uncovered_loss,
                    r.late_adjustments,
                    r.paid,
                    r.share_due,
                ]
                for r in report.rows
            ],
            totals=[
                "Total",
                totals.lots,
                totals.contributed,
                totals.loss_deducted,
                totals.returned,
                totals.capital_outstanding,
                totals.share,
                totals.uncovered_loss,
                totals.late_adjustments,
                totals.paid,
                totals.share_due,
            ],
        )
        return _xlsx(f"partenaires-{report.date_from}-{report.date_to}", content)
