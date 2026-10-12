from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.views import APIView

from apps.core.models import Membership, Organization, Role
from apps.core.permissions import HasRole, membership_of
from apps.reports import exports, selectors

from .serializers import (
    LossReportSerializer,
    PeriodQuerySerializer,
    SalesQuerySerializer,
    SalesReportSerializer,
    SlowQuerySerializer,
    SlowReportSerializer,
    StockValueReportSerializer,
)

ZERO = Decimal("0.000")


class ReadsReports(HasRole):
    """Reports are for the office: the owner, the manager and the accountant (never a driver)."""

    roles = frozenset({Role.OWNER, Role.MANAGER, Role.ACCOUNTANT})


class ReportView(APIView):
    permission_classes: tuple[type[BasePermission], ...] = (ReadsReports,)
    query_serializer: type[Serializer[Any]]

    @property
    def membership(self) -> Membership:
        membership = membership_of(self.request)
        assert membership is not None  # guaranteed by the permission class
        return membership

    @property
    def organization(self) -> Organization:
        return self.membership.organization

    def query(self, request: Request) -> dict[str, Any]:
        serializer = self.query_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return dict(serializer.validated_data)


def _xlsx(name: str, content: bytes) -> HttpResponse:
    response = HttpResponse(content, content_type=exports.XLSX_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{name}.xlsx"'
    return response


def _sum(rows: Sequence[Any], field: str) -> Decimal:
    return sum((getattr(row, field) for row in rows), ZERO)


PERIOD_PARAMS = [
    OpenApiParameter("date_from", OpenApiTypes.DATE, description="First day (default: first of this month)."),
    OpenApiParameter("date_to", OpenApiTypes.DATE, description="Last day, inclusive (default: today)."),
]
SALES_PARAMS = [OpenApiParameter("group_by", str, enum=list(selectors.GROUPS)), *PERIOD_PARAMS]
SLOW_PARAMS = [OpenApiParameter("days", int, description="Days without movement (default 30).")]


# ---- Sales ----


class SalesReportView(ReportView):
    query_serializer = SalesQuerySerializer

    def report(self, request: Request) -> selectors.SalesReport:
        query = self.query(request)
        return selectors.sales_report(
            self.organization, group_by=query["group_by"], date_from=query["date_from"], date_to=query["date_to"]
        )

    @extend_schema(operation_id="getSalesReport", parameters=SALES_PARAMS, responses=SalesReportSerializer)
    def get(self, request: Request) -> Response:
        """Confirmed sales (BL) by customer, product, truck, driver, day, week or month: kilos, revenue without
        VAT, cost of goods sold and margin, net of the credit notes issued in the period. The same rows as the
        monthly closing, so the totals always agree with it."""
        return Response(SalesReportSerializer(self.report(request)).data)


class SalesReportExportView(SalesReportView):
    @extend_schema(operation_id="exportSalesReport", parameters=SALES_PARAMS, responses=OpenApiTypes.BINARY)
    def get(self, request: Request) -> HttpResponse:  # type: ignore[override]
        """The sales report as an Excel file."""
        report = self.report(request)
        totals = report.totals
        content = exports.workbook_bytes(
            title="Ventes",
            headers=["Libellé", "Ventes", "Kg", "Chiffre d'affaires HT", "Coût des marchandises", "Marge"],
            rows=[[r.name, r.sales, r.quantity, r.revenue, r.cogs, r.margin] for r in report.rows],
            totals=["Total", totals.sales, totals.quantity, totals.revenue, totals.cogs, totals.margin],
        )
        return _xlsx(f"ventes-{report.group_by}-{report.date_from}-{report.date_to}", content)


# ---- Stock value ----


def stock_value_payload(organization: Organization) -> dict[str, Any]:
    rows = selectors.stock_value(organization)
    return {"rows": rows, "total_quantity": _sum(rows, "quantity"), "total_value": _sum(rows, "value")}


class StockValueReportView(ReportView):
    query_serializer = PeriodQuerySerializer

    @extend_schema(operation_id="getStockValueReport", responses=StockValueReportSerializer)
    def get(self, request: Request) -> Response:
        """What each place (cold rooms and trucks) holds now, per product, valued at the purchase cost of
        each lot. Unsold stock is an asset, not a cost."""
        return Response(StockValueReportSerializer(stock_value_payload(self.organization)).data)


class StockValueExportView(ReportView):
    query_serializer = PeriodQuerySerializer

    @extend_schema(operation_id="exportStockValueReport", responses=OpenApiTypes.BINARY)
    def get(self, request: Request) -> HttpResponse:
        """The stock value report as an Excel file."""
        payload = stock_value_payload(self.organization)
        content = exports.workbook_bytes(
            title="Valeur du stock",
            headers=["Emplacement", "Produit", "Kg", "Valeur au coût d'achat"],
            rows=[[r.location_name, r.product_name, r.quantity, r.value] for r in payload["rows"]],
            totals=["Total", "", payload["total_quantity"], payload["total_value"]],
        )
        return _xlsx(f"valeur-stock-{timezone.localdate()}", content)


# ---- Slow-moving lots ----


def slow_payload(organization: Organization, days: int) -> dict[str, Any]:
    rows = selectors.slow_moving(organization, days=days, today=timezone.localdate())
    return {"days": days, "rows": rows, "total_quantity": _sum(rows, "quantity"), "total_value": _sum(rows, "value")}


class SlowMovingReportView(ReportView):
    query_serializer = SlowQuerySerializer

    @extend_schema(operation_id="getSlowMovingReport", parameters=SLOW_PARAMS, responses=SlowReportSerializer)
    def get(self, request: Request) -> Response:
        """Lots still on hand that nothing has touched for `days` days or more, longest idle first."""
        return Response(SlowReportSerializer(slow_payload(self.organization, self.query(request)["days"])).data)


class SlowMovingExportView(ReportView):
    query_serializer = SlowQuerySerializer

    @extend_schema(operation_id="exportSlowMovingReport", parameters=SLOW_PARAMS, responses=OpenApiTypes.BINARY)
    def get(self, request: Request) -> HttpResponse:
        """The slow-moving lots as an Excel file."""
        days = self.query(request)["days"]
        payload = slow_payload(self.organization, days)
        content = exports.workbook_bytes(
            title="Stock dormant",
            headers=["Lot", "Produit", "Fournisseur", "Reçu le", "Dernier mouvement", "Jours", "Kg", "Valeur"],
            rows=[
                [
                    r.batch_number,
                    r.product_name,
                    r.supplier_name,
                    r.received_on,
                    r.last_movement_on,
                    r.days_idle,
                    r.quantity,
                    r.value,
                ]
                for r in payload["rows"]
            ],
            totals=["Total", "", "", "", "", "", payload["total_quantity"], payload["total_value"]],
        )
        return _xlsx(f"stock-dormant-{days}j-{timezone.localdate()}", content)


# ---- Losses and weight differences ----


def losses_payload(organization: Organization, query: dict[str, Any]) -> dict[str, Any]:
    rows = selectors.losses(organization, date_from=query["date_from"], date_to=query["date_to"])
    return {
        "date_from": query["date_from"],
        "date_to": query["date_to"],
        "rows": rows,
        "total_lost_quantity": _sum(rows, "lost_quantity"),
        "total_lost_value": _sum(rows, "lost_value"),
    }


class LossesReportView(ReportView):
    query_serializer = PeriodQuerySerializer

    @extend_schema(operation_id="getLossesReport", parameters=PERIOD_PARAMS, responses=LossReportSerializer)
    def get(self, request: Request) -> Response:
        """Per product: kilos written off as losses, and the net weight differences found by counts and
        adjustments, at the lot's cost per kg."""
        return Response(LossReportSerializer(losses_payload(self.organization, self.query(request))).data)


class LossesReportExportView(ReportView):
    query_serializer = PeriodQuerySerializer

    @extend_schema(operation_id="exportLossesReport", parameters=PERIOD_PARAMS, responses=OpenApiTypes.BINARY)
    def get(self, request: Request) -> HttpResponse:
        """The losses and differences report as an Excel file."""
        payload = losses_payload(self.organization, self.query(request))
        content = exports.workbook_bytes(
            title="Pertes et écarts",
            headers=["Produit", "Pertes (kg)", "Pertes (valeur)", "Écarts de poids (kg)", "Écarts de poids (valeur)"],
            rows=[
                [r.product_name, r.lost_quantity, r.lost_value, r.difference_quantity, r.difference_value]
                for r in payload["rows"]
            ],
            totals=["Total", payload["total_lost_quantity"], payload["total_lost_value"], "", ""],
        )
        return _xlsx(f"pertes-{payload['date_from']}-{payload['date_to']}", content)
