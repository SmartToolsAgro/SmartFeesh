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
from apps.purchasing import selectors, services
from apps.purchasing.models import GoodsReceipt, GoodsReceiptLine

from .serializers import (
    DifferenceFilterSerializer,
    DifferenceLineSerializer,
    LastCostFilterSerializer,
    LastCostSerializer,
    ReceiptFilterSerializer,
    ReceiptSerializer,
    ReceiptWriteSerializer,
)


# Purchases are office data (D-032): owner, manager and accountant read; owner and manager record; drivers 403.
# Rows of the user's organization only (D-022). A comment, not a docstring: it would describe every endpoint.
class PurchasingView(APIView):
    permission_classes = (ReadOfficeWriteOwnerOrManager,)

    @property
    def membership(self) -> Membership:
        membership = membership_of(self.request)
        assert membership is not None  # guaranteed by the permission class
        return membership

    @property
    def organization(self) -> Organization:
        return self.membership.organization


def _resolved(organization: Organization, data: dict[str, Any]) -> dict[str, Any]:
    """The ids of a receipt replaced by the rows they name in the organization; unknown ids are field errors."""
    errors: dict[str, str] = {}
    supplier = location = None
    try:
        supplier = partners.supplier_of(organization, data["supplier"])
    except ObjectDoesNotExist:
        errors["supplier"] = _("Fournisseur inconnu.")
    try:
        location = inventory.location_of(organization, data["location"])
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
    return {**data, "supplier": supplier, "location": location, "lines": lines}


class ReceiptListView(PurchasingView, ListAPIView[GoodsReceipt]):
    serializer_class = ReceiptSerializer
    pagination_class = PagedList

    def get_queryset(self) -> QuerySet[GoodsReceipt]:
        filters = ReceiptFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return selectors.receipts_of(
            self.organization,
            supplier_id=filters.validated_data.get("supplier"),
            search=filters.validated_data["search"],
            with_differences=filters.validated_data["differences"],
        )

    @extend_schema(operation_id="listReceipts", parameters=[ReceiptFilterSerializer])
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Goods receipts, newest first, paginated (`limit`, `offset`), each with its lines and totals.
        Filter by supplier, by `search` (number, supplier's reference, supplier name) or to receipts with
        a weight difference."""
        return super().get(request, *args, **kwargs)

    @extend_schema(operation_id="createReceipt", request=ReceiptWriteSerializer, responses={201: ReceiptSerializer})
    def post(self, request: Request) -> Response:
        """Record goods received from a supplier: one batch per line, its accepted net weight into stock.
        Errors of a line come back on `lines.<index>.<field>`."""
        serializer = ReceiptWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = _resolved(self.organization, serializer.validated_data)
        receipt = services.create_receipt(organization=self.organization, actor=self.membership.user, **data)
        return Response(
            ReceiptSerializer(selectors.receipt_of(self.organization, receipt.pk)).data,
            status=status.HTTP_201_CREATED,
        )


class ReceiptDetailView(PurchasingView):
    @extend_schema(operation_id="getReceipt", responses=ReceiptSerializer)
    def get(self, request: Request, receipt_id: int) -> Response:
        try:
            receipt = selectors.receipt_of(self.organization, receipt_id)
        except GoodsReceipt.DoesNotExist:
            raise Http404 from None
        return Response(ReceiptSerializer(receipt).data)


class ReceiptDifferenceListView(PurchasingView, ListAPIView[GoodsReceiptLine]):
    serializer_class = DifferenceLineSerializer
    pagination_class = PagedList

    def get_queryset(self) -> QuerySet[GoodsReceiptLine]:
        filters = DifferenceFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return selectors.difference_lines(
            self.organization,
            supplier_id=filters.validated_data.get("supplier"),
            date_from=filters.validated_data.get("date_from"),
            date_to=filters.validated_data.get("date_to"),
        )

    @extend_schema(operation_id="listReceiptDifferences", parameters=[DifferenceFilterSerializer])
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Weight differences report: receipt lines whose accepted weight is not the invoiced or ordered
        weight, newest first, paginated. Filter by supplier and by receipt dates (inclusive)."""
        return super().get(request, *args, **kwargs)


class LastCostListView(PurchasingView):
    @extend_schema(
        operation_id="listLastPurchaseCosts",
        parameters=[LastCostFilterSerializer],
        responses=LastCostSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        """What was last paid one supplier for each product (its latest batch). The receipt form suggests
        it and shows the change. The full history per product and supplier is `listBatches`."""
        filters = LastCostFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        batches = inventory.last_batches_from(self.organization, supplier_id=filters.validated_data["supplier"])
        return Response(LastCostSerializer(batches, many=True).data)
