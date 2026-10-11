from typing import Any

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import QuerySet
from django.http import Http404
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog import selectors as catalog
from apps.core.api.pagination import PagedList
from apps.core.models import Membership, Organization
from apps.core.permissions import ReadOfficeWriteOwnerOrManager, membership_of
from apps.inventory import selectors as inventory
from apps.partners import selectors as partners
from apps.sales import selectors, services
from apps.sales.models import Quote

from .serializers import (
    QuoteDetailSerializer,
    QuoteFilterSerializer,
    QuoteRefuseSerializer,
    QuoteSerializer,
    QuoteWriteSerializer,
)


# Quotes are office documents (D-050): owner, manager and accountant read, owner and manager write, drivers
# get 403. Rows of the user's organization only (D-022). A comment, not a docstring: a docstring would
# describe every endpoint in the schema.
class OfficeView(APIView):
    permission_classes = (ReadOfficeWriteOwnerOrManager,)

    @property
    def membership(self) -> Membership:
        membership = membership_of(self.request)
        assert membership is not None  # guaranteed by the permission class
        return membership

    @property
    def organization(self) -> Organization:
        return self.membership.organization


# ---- Quotes (P2-T03) ----


def _quote_fields(organization: Organization, data: dict[str, Any]) -> dict[str, Any]:
    """The ids of a quote replaced by the rows they name in the organization; unknown ids are field errors."""
    errors: dict[str, str] = {}
    fields = {key: value for key, value in data.items() if key != "send_now"}
    try:
        fields["customer"] = partners.customer_of(organization, data["customer"])
    except ObjectDoesNotExist:
        errors["customer"] = _("Client inconnu.")
    if data["location"] is not None:
        try:
            fields["location"] = inventory.location_of(organization, data["location"])
        except ObjectDoesNotExist:
            errors["location"] = _("Emplacement inconnu.")
    lines = []
    for index, line in enumerate(data["lines"]):
        try:
            product = catalog.product_of(organization, line["product"])
        except ObjectDoesNotExist:
            errors[services.line_error_key(index, "product")] = _("Produit inconnu.")
            continue
        lines.append({**line, "product": product})
    if errors:
        raise ValidationError(errors)
    return {**fields, "lines": lines, "send": data["send_now"]}


def _quote_answer(organization: Organization, quote_id: int, *, status_code: int = status.HTTP_200_OK) -> Response:
    return Response(QuoteDetailSerializer(selectors.quote_of(organization, quote_id)).data, status=status_code)


class QuoteView(OfficeView):
    def quote(self, quote_id: int) -> Quote:
        try:
            return selectors.quote_of(self.organization, quote_id)
        except Quote.DoesNotExist:
            raise Http404 from None


class QuoteListView(QuoteView, ListAPIView[Quote]):
    serializer_class = QuoteSerializer
    pagination_class = PagedList

    def get_queryset(self) -> QuerySet[Quote]:
        filters = QuoteFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return selectors.quotes_of(
            self.organization,
            status=filters.validated_data.get("status"),
            customer_id=filters.validated_data.get("customer"),
            date_from=filters.validated_data.get("date_from"),
            date_to=filters.validated_data.get("date_to"),
            search=filters.validated_data["search"],
        )

    @extend_schema(operation_id="listQuotes", parameters=[QuoteFilterSerializer])
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Quotes, newest first, paginated (`limit`, `offset`). Filter by status (a sent quote past its
        validity date counts as expired), customer, days (inclusive) or `search` (number, customer)."""
        return super().get(request, *args, **kwargs)

    @extend_schema(operation_id="createQuote", request=QuoteWriteSerializer, responses={201: QuoteDetailSerializer})
    def post(self, request: Request) -> Response:
        """Prepare a quote (a draft), or with `send_now` mark it sent at once. A line without `unit_price`
        takes the sale price in force on the quote's day; without `valid_until` it is valid 3 days.
        Errors of a line come back on `lines.<index>.<field>`."""
        serializer = QuoteWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = _quote_fields(self.organization, serializer.validated_data)
        quote = services.create_quote(organization=self.organization, actor=self.membership.user, **data)
        return _quote_answer(self.organization, quote.pk, status_code=status.HTTP_201_CREATED)


class QuoteDetailView(QuoteView):
    @extend_schema(operation_id="getQuote", responses=QuoteDetailSerializer)
    def get(self, request: Request, quote_id: int) -> Response:
        """One quote with its lines and totals (without VAT until P2-T05)."""
        return _quote_answer(self.organization, self.quote(quote_id).pk)

    @extend_schema(operation_id="updateQuote", request=QuoteWriteSerializer, responses=QuoteDetailSerializer)
    def put(self, request: Request, quote_id: int) -> Response:
        """Change a draft (every line is replaced), and with `send_now` send it too. A sent quote no longer
        changes."""
        quote = self.quote(quote_id)
        serializer = QuoteWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = _quote_fields(self.organization, serializer.validated_data)
        services.update_quote(quote=quote, actor=self.membership.user, **data)
        return _quote_answer(self.organization, quote.pk)


class QuoteSendView(QuoteView):
    @extend_schema(operation_id="sendQuote", request=None, responses=QuoteDetailSerializer)
    def post(self, request: Request, quote_id: int) -> Response:
        """Mark a draft as given to the customer: it no longer changes. Refused once its validity date has
        passed."""
        services.send_quote(quote=self.quote(quote_id), actor=self.membership.user)
        return _quote_answer(self.organization, quote_id)


class QuoteAcceptView(QuoteView):
    @extend_schema(operation_id="acceptQuote", request=None, responses=QuoteDetailSerializer)
    def post(self, request: Request, quote_id: int) -> Response:
        """Record the customer's yes on a sent quote, up to its validity date included. No stock is
        reserved; the sale comes from it in P2-T04."""
        services.accept_quote(quote=self.quote(quote_id), actor=self.membership.user)
        return _quote_answer(self.organization, quote_id)


class QuoteRefuseView(QuoteView):
    @extend_schema(operation_id="refuseQuote", request=QuoteRefuseSerializer, responses=QuoteDetailSerializer)
    def post(self, request: Request, quote_id: int) -> Response:
        """Record the customer's no on a sent quote, with an optional reason."""
        serializer = QuoteRefuseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.refuse_quote(
            quote=self.quote(quote_id), actor=self.membership.user, reason=serializer.validated_data["reason"]
        )
        return _quote_answer(self.organization, quote_id)
