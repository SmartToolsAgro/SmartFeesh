"""The statement PDF of one customer or one supplier over chosen dates (D-156): made on the spot."""

import datetime as dt
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.request import Request

from apps.documents import services as documents
from apps.reports import statements

from .views import ReportView

STATEMENT_PARAMS = [
    OpenApiParameter("date_from", OpenApiTypes.DATE, description="First day; empty: from the beginning."),
    OpenApiParameter("date_to", OpenApiTypes.DATE, description="Last day, inclusive (default: today)."),
]


class StatementQuerySerializer(serializers.Serializer):  # type: ignore[type-arg]
    """`date_from` (empty: from the beginning) and `date_to` (inclusive, default today)."""

    date_from = serializers.DateField(required=False, allow_null=True, default=None)
    date_to = serializers.DateField(required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        last = attrs.get("date_to") or timezone.localdate()
        first = attrs.get("date_from")
        if first is not None and last < first:
            raise serializers.ValidationError("La date de fin précède la date de début.")
        attrs["date_to"] = last
        return attrs


def _pdf(document: documents.Printable, organization: Any) -> HttpResponse:
    response = HttpResponse(documents.render_pdf(document, organization), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{document.filename}"'
    response["Cache-Control"] = "private, no-store"
    return response


class StatementView(ReportView):
    query_serializer = StatementQuerySerializer

    def dates(self, request: Request) -> tuple[dt.date | None, dt.date]:
        query = self.query(request)
        return query["date_from"], query["date_to"]


class CustomerStatementPdfView(StatementView):
    @extend_schema(
        operation_id="getCustomerStatementPdf",
        parameters=STATEMENT_PARAMS,
        responses={(200, "application/pdf"): OpenApiTypes.BINARY},
    )
    def get(self, request: Request, customer_id: int) -> HttpResponse:
        """The customer's statement as a PDF: every sale with its products, kilos and prices, the payments, the
        account with its running balance, the boxes they hold, and a summary. Office roles; drivers get 403."""
        date_from, date_to = self.dates(request)
        try:
            document = statements.customer_statement_printable(
                self.organization, customer_id, date_from=date_from, date_to=date_to
            )
        except ObjectDoesNotExist:
            raise Http404 from None
        return _pdf(document, self.organization)


class SupplierStatementPdfView(StatementView):
    @extend_schema(
        operation_id="getSupplierStatementPdf",
        parameters=STATEMENT_PARAMS,
        responses={(200, "application/pdf"): OpenApiTypes.BINARY},
    )
    def get(self, request: Request, supplier_id: int) -> HttpResponse:
        """The supplier's statement as a PDF: every receipt with its products, kilos and prices, the invoices and
        payments as an account with its running balance, the boxes we owe them, and a summary. Office roles."""
        date_from, date_to = self.dates(request)
        try:
            document = statements.supplier_statement_printable(
                self.organization, supplier_id, date_from=date_from, date_to=date_to
            )
        except ObjectDoesNotExist:
            raise Http404 from None
        return _pdf(document, self.organization)
