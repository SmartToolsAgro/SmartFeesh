from decimal import Decimal
from typing import Any

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import QuerySet
from django.http import Http404
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog import selectors as catalog
from apps.core.api.pagination import PagedList
from apps.core.models import Membership, Organization, Role
from apps.core.permissions import HasRole, IsOwnerOrManager, ReadOfficeWriteOwnerOrManager, membership_of
from apps.fleet import selectors as fleet
from apps.inventory import selectors as inventory
from apps.partners import selectors as partners
from apps.sales import selectors, services
from apps.sales.models import Quote, Sale

from .serializers import (
    BatchSalesSerializer,
    QuoteConvertSerializer,
    QuoteDetailSerializer,
    QuoteFilterSerializer,
    QuoteRefuseSerializer,
    QuoteSerializer,
    QuoteWriteSerializer,
    SaleCancelSerializer,
    SaleDetailSerializer,
    SaleFilterSerializer,
    SaleSerializer,
    SaleWriteSerializer,
)


# Quotes are office documents (D-050): owner, manager and accountant read, owner and manager write, drivers
# get 403. Rows of the user's organization only (D-022). A comment, not a docstring: a docstring would
# describe every endpoint in the schema.
class OfficeView(APIView):
    permission_classes: tuple[type[BasePermission], ...] = (ReadOfficeWriteOwnerOrManager,)

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


# ---- Sales (P2-T04) ----

SELLER_ROLES = frozenset({Role.OWNER, Role.MANAGER, Role.DRIVER})


class SalesPermission(HasRole):
    """Owners, managers and the accountant read sales; owners, managers and drivers sell. What a driver may
    see and where they may sell is checked by the views (their own sales, their truck of the day)."""

    roles = frozenset({Role.OWNER, Role.MANAGER, Role.ACCOUNTANT, Role.DRIVER})

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not super().has_permission(request, view):
            return False
        membership = membership_of(request)
        return request.method in SAFE_METHODS or (membership is not None and membership.role in SELLER_ROLES)


def _payment(data: dict[str, Any]) -> services.PaymentFields:
    return {
        "amount_paid": data["amount_paid"],
        "paid_in_full": data["paid_in_full"],
        "payment_method": data["payment_method"],
        "payment_reference": data["payment_reference"],
    }


class SaleView(OfficeView):
    permission_classes: tuple[type[BasePermission], ...] = (SalesPermission,)

    @property
    def is_driver(self) -> bool:
        return self.membership.role == Role.DRIVER

    def sales(self) -> QuerySet[Sale]:
        # A driver sees the sales they made, nothing else.
        created_by_id = self.membership.user_id if self.is_driver else None
        return selectors.sales_of(self.organization, created_by_id=created_by_id)

    def sale(self, sale_id: int) -> Sale:
        try:
            return self.sales().get(pk=sale_id)
        except Sale.DoesNotExist:
            raise Http404 from None

    def answer(self, sale_id: int, *, status_code: int = status.HTTP_200_OK) -> Response:
        data = SaleDetailSerializer(self.sale(sale_id), context={"show_costs": not self.is_driver}).data
        return Response(data, status=status_code)

    def check_location(self, location_id: int) -> None:
        """A driver sells only from the truck of their day (D-042, D-046)."""
        if not fleet.may_use_location(self.membership, location_id):
            raise PermissionDenied(_("Un chauffeur ne vend que depuis son camion du jour."))

    def sale_fields(self, data: dict[str, Any]) -> dict[str, Any]:
        """The ids of a sale replaced by the rows they name in the organization; unknown ids are field errors."""
        errors: dict[str, str] = {}
        organization = self.organization
        self.check_location(data["location"])
        fields: dict[str, Any] = {"customer": None, "notes": data["notes"], "payment": _payment(data)}
        if data["customer"] is not None:
            try:
                fields["customer"] = partners.customer_of(organization, data["customer"])
            except ObjectDoesNotExist:
                errors["customer"] = _("Client inconnu.")
        try:
            fields["location"] = inventory.location_of(organization, data["location"])
        except ObjectDoesNotExist:
            errors["location"] = _("Emplacement inconnu.")
        if self.is_driver:
            # A driver sells now, from the truck of the day: the moment is the server's.
            fields["sold_at"] = None
        else:
            fields["sold_at"] = data["sold_at"]
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
        return {**fields, "lines": lines, "confirm": data["confirm_now"]}

    def check_own_place(self, sale: Sale) -> None:
        if self.is_driver:
            self.check_location(sale.location_id)


class SaleListView(SaleView, ListAPIView[Sale]):
    serializer_class = SaleSerializer
    pagination_class = PagedList

    def get_serializer_context(self) -> dict[str, Any]:
        return {**super().get_serializer_context(), "show_costs": not self.is_driver}

    def get_queryset(self) -> QuerySet[Sale]:
        filters = SaleFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return selectors.sales_of(
            self.organization,
            status=filters.validated_data.get("status"),
            customer_id=filters.validated_data.get("customer"),
            location_id=filters.validated_data.get("location"),
            created_by_id=self.membership.user_id if self.is_driver else None,
            date_from=filters.validated_data.get("date_from"),
            date_to=filters.validated_data.get("date_to"),
            search=filters.validated_data["search"],
        )

    @extend_schema(operation_id="listSales", parameters=[SaleFilterSerializer])
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Sales, newest first, paginated (`limit`, `offset`). Filter by status, customer, place, days of the
        sale (inclusive) or `search` (number, customer). A driver sees only their own sales, without costs."""
        return super().get(request, *args, **kwargs)

    @extend_schema(operation_id="createSale", request=SaleWriteSerializer, responses={201: SaleDetailSerializer})
    def post(self, request: Request) -> Response:
        """Type a sale (a draft), or with `confirm_now` confirm it at once: the stock leaves oldest batch first
        and the customer owes what is not paid. Without `customer` it is the walk-in customer (counter sale,
        who pays everything). A line without `unit_price` takes the customer's price in force at `sold_at`.
        Errors of a line come back on `lines.<index>.<field>`. A driver sells only from their truck of the
        day, at the present moment."""
        serializer = SaleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = self.sale_fields(serializer.validated_data)
        sale = services.create_sale(
            organization=self.organization,
            actor=self.membership.user,
            client_uuid=serializer.validated_data["client_uuid"],
            **data,
        )
        return self.answer(sale.pk, status_code=status.HTTP_201_CREATED)


class SaleDetailView(SaleView):
    @extend_schema(operation_id="getSale", responses=SaleDetailSerializer)
    def get(self, request: Request, sale_id: int) -> Response:
        """One sale with its lines and, once confirmed, the lots each line came from with their cost (not
        shown to drivers). Totals are without VAT until P2-T05."""
        return self.answer(self.sale(sale_id).pk)

    @extend_schema(operation_id="updateSale", request=SaleWriteSerializer, responses=SaleDetailSerializer)
    def put(self, request: Request, sale_id: int) -> Response:
        """Change a draft (every line is replaced), and with `confirm_now` confirm it too. A confirmed sale no
        longer changes: cancel it instead."""
        sale = self.sale(sale_id)
        self.check_own_place(sale)
        serializer = SaleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = self.sale_fields(serializer.validated_data)
        services.update_sale(sale=sale, actor=self.membership.user, **data)
        return self.answer(sale.pk)


class SaleConfirmView(SaleView):
    @extend_schema(operation_id="confirmSale", request=None, responses=SaleDetailSerializer)
    def post(self, request: Request, sale_id: int) -> Response:
        """Confirm a draft: the stock leaves oldest batch first and the customer owes what is not paid. Refused
        as a whole when the place holds too little (`lines.<index>.quantity`)."""
        sale = self.sale(sale_id)
        self.check_own_place(sale)
        services.confirm_sale(sale=sale, actor=self.membership.user)
        return self.answer(sale_id)


class SaleCancelView(SaleView):
    permission_classes = (IsOwnerOrManager,)

    @extend_schema(operation_id="cancelSale", request=SaleCancelSerializer, responses=SaleDetailSerializer)
    def post(self, request: Request, sale_id: int) -> Response:
        """Cancel a sale (owner or manager). A confirmed sale needs a reason: its kilos come back to the same
        lots at the same place; the sale stays, marked cancelled."""
        serializer = SaleCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.cancel_sale(
            sale=self.sale(sale_id), actor=self.membership.user, reason=serializer.validated_data["reason"]
        )
        return self.answer(sale_id)


class QuoteConvertView(QuoteView):
    @extend_schema(
        operation_id="convertQuoteToSale", request=QuoteConvertSerializer, responses={201: SaleDetailSerializer}
    )
    def post(self, request: Request, quote_id: int) -> Response:
        """Turn an accepted quote, still valid, into a sale (a draft, or confirmed with `confirm_now`): same
        customer, products, kg, prices and discounts, from the quote's place unless `location` is given. The
        quote stays accepted and links to its sale."""
        quote = self.quote(quote_id)
        serializer = QuoteConvertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        location = None
        if data["location"] is not None:
            try:
                location = inventory.location_of(self.organization, data["location"])
            except ObjectDoesNotExist:
                raise ValidationError({"location": _("Emplacement inconnu.")}) from None
        sale = services.create_sale_from_quote(
            quote=quote,
            actor=self.membership.user,
            location=location,
            sold_at=data["sold_at"],
            payment=_payment(data),
            confirm=data["confirm_now"],
        )
        detail = SaleDetailSerializer(selectors.sale_of(self.organization, sale.pk)).data
        return Response(detail, status=status.HTTP_201_CREATED)


class BatchSalesView(OfficeView):
    @extend_schema(operation_id="getBatchSales", responses=BatchSalesSerializer)
    def get(self, request: Request, batch_id: int) -> Response:
        """What one lot sold over its confirmed sales: kg, revenue without VAT, cost of the goods and margin,
        then each sale line that took from it (oldest first). Office data: drivers get 403."""
        try:
            batch = inventory.batch_of(self.organization, batch_id)
        except ObjectDoesNotExist:
            raise Http404 from None
        totals = selectors.batch_sales_totals(self.organization, batch_ids=[batch.pk]).get(batch.pk)
        zero = Decimal("0.000")
        data = {
            "batch_id": batch.pk,
            "quantity": totals.quantity if totals else zero,
            "revenue": totals.revenue if totals else zero,
            "cost": totals.cost if totals else zero,
            "margin": totals.margin if totals else zero,
            "rows": selectors.batch_sales(self.organization, batch_id=batch.pk),
        }
        return Response(BatchSalesSerializer(data).data)
