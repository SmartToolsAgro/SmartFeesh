from decimal import Decimal
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
from apps.inventory import selectors, services
from apps.inventory.models import Batch, StockLocation, Transfer

from .serializers import (
    BatchFilterSerializer,
    BatchSerializer,
    LocationStockSerializer,
    StockLocationCreateSerializer,
    StockLocationFilterSerializer,
    StockLocationSerializer,
    StockLocationUpdateSerializer,
    TransferDetailSerializer,
    TransferFilterSerializer,
    TransferSerializer,
    TransferWriteSerializer,
    TruckDayFilterSerializer,
    TruckDaySerializer,
)


# Rows of the user's organization only (D-022); drivers get 403 and read their own truck from `/me`.
# A comment, not a docstring: a docstring would describe every endpoint in the schema.
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


class LocationView(OfficeView):
    def location(self, location_id: int) -> StockLocation:
        try:
            return selectors.location_of(self.organization, location_id)
        except StockLocation.DoesNotExist:
            raise Http404 from None

    def standalone_location(self, location_id: int) -> StockLocation:
        """A location changed on its own: a truck's location changes through its truck."""
        location = self.location(location_id)
        if location.kind not in selectors.STANDALONE_KINDS:
            raise ValidationError(_("Un camion se modifie depuis la liste des camions."))
        return location


class LocationListView(LocationView):
    @extend_schema(
        operation_id="listLocations",
        parameters=[StockLocationFilterSerializer],
        responses=StockLocationSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        """Cold rooms, trucks and other locations, sorted by kind then name. Archived ones only when asked."""
        filters = StockLocationFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        kind = filters.validated_data.get("kind")
        locations = selectors.locations_of(
            self.organization, kinds=[kind] if kind else None, status=filters.validated_data["status"]
        )
        return Response(StockLocationSerializer(locations, many=True).data)

    @extend_schema(
        operation_id="createLocation",
        request=StockLocationCreateSerializer,
        responses={201: StockLocationSerializer},
    )
    def post(self, request: Request) -> Response:
        """A new cold room or other location. A truck is created with `createTruck`."""
        serializer = StockLocationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location = services.create_location(
            organization=self.organization, actor=self.membership.user, **serializer.validated_data
        )
        return Response(StockLocationSerializer(location).data, status=status.HTTP_201_CREATED)


class LocationDetailView(LocationView):
    @extend_schema(operation_id="getLocation", responses=StockLocationSerializer)
    def get(self, request: Request, location_id: int) -> Response:
        return Response(StockLocationSerializer(self.location(location_id)).data)

    @extend_schema(
        operation_id="updateLocation", request=StockLocationUpdateSerializer, responses=StockLocationSerializer
    )
    def patch(self, request: Request, location_id: int) -> Response:
        """Rename a cold room or other location, or change whether it sells at the counter."""
        location = self.standalone_location(location_id)
        serializer = StockLocationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location = services.update_location(location=location, actor=self.membership.user, **serializer.validated_data)
        return Response(StockLocationSerializer(location).data)


class LocationArchiveView(LocationView):
    @extend_schema(operation_id="archiveLocation", request=None, responses=StockLocationSerializer)
    def post(self, request: Request, location_id: int) -> Response:
        """An archived location keeps its history but receives no more stock."""
        location = services.set_location_active(
            location=self.standalone_location(location_id), actor=self.membership.user, is_active=False
        )
        return Response(StockLocationSerializer(location).data)


class LocationRestoreView(LocationView):
    @extend_schema(operation_id="restoreLocation", request=None, responses=StockLocationSerializer)
    def post(self, request: Request, location_id: int) -> Response:
        location = services.set_location_active(
            location=self.standalone_location(location_id), actor=self.membership.user, is_active=True
        )
        return Response(StockLocationSerializer(location).data)


class BatchListView(OfficeView, ListAPIView[Batch]):
    serializer_class = BatchSerializer
    pagination_class = PagedList

    def get_queryset(self) -> QuerySet[Batch]:
        filters = BatchFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return selectors.batches_of(
            self.organization,
            product_id=filters.validated_data.get("product"),
            supplier_id=filters.validated_data.get("supplier"),
            search=filters.validated_data["search"],
        )

    @extend_schema(operation_id="listBatches", parameters=[BatchFilterSerializer])
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Batches, newest receipt first, paginated (`limit`, `offset`). Filter by product or supplier;
        `search` matches the batch number, the supplier's receipt reference, product and supplier.
        Batches are created by goods receipts, not here."""
        return super().get(request, *args, **kwargs)


class BatchDetailView(OfficeView):
    @extend_schema(operation_id="getBatch", responses=BatchSerializer)
    def get(self, request: Request, batch_id: int) -> Response:
        try:
            batch = selectors.batch_of(self.organization, batch_id)
        except Batch.DoesNotExist:
            raise Http404 from None
        return Response(BatchSerializer(batch).data)


class LocationStockView(LocationView):
    @extend_schema(operation_id="listLocationStock", responses=LocationStockSerializer(many=True))
    def get(self, request: Request, location_id: int) -> Response:
        """What a location holds now per product, all batches together, by product name."""
        location = self.location(location_id)
        rows = selectors.location_stock(self.organization, location_id=location.pk)
        return Response(LocationStockSerializer(rows, many=True).data)


# ---- Transfers (P1-T09) ----


def _transfer_fields(organization: Organization, data: dict[str, Any]) -> dict[str, Any]:
    """The ids of a transfer replaced by the rows they name in the organization; unknown ids are field errors."""
    errors: dict[str, str] = {}
    places: dict[str, StockLocation] = {}
    for field in ("from_location", "to_location"):
        try:
            places[field] = selectors.location_of(organization, data[field])
        except StockLocation.DoesNotExist:
            errors[field] = _("Emplacement inconnu.")
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
    fields = {key: value for key, value in data.items() if key != "validate_now"}
    return {**fields, **places, "lines": lines, "validate": data["validate_now"]}


def _transfer_answer(
    organization: Organization, transfer_id: int, *, status_code: int = status.HTTP_200_OK
) -> Response:
    transfer = selectors.transfer_of(organization, transfer_id)
    movements = selectors.movements_from_sources(list(transfer.lines.all()))
    return Response(TransferDetailSerializer(transfer, context={"movements": movements}).data, status=status_code)


class TransferView(OfficeView):
    def transfer(self, transfer_id: int) -> Transfer:
        try:
            return selectors.transfer_of(self.organization, transfer_id)
        except Transfer.DoesNotExist:
            raise Http404 from None


class TransferListView(TransferView, ListAPIView[Transfer]):
    serializer_class = TransferSerializer
    pagination_class = PagedList

    def get_queryset(self) -> QuerySet[Transfer]:
        filters = TransferFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return selectors.transfers_of(
            self.organization,
            kind=filters.validated_data.get("kind"),
            status=filters.validated_data.get("status"),
            location_id=filters.validated_data.get("location"),
            date_from=filters.validated_data.get("date_from"),
            date_to=filters.validated_data.get("date_to"),
            search=filters.validated_data["search"],
        )

    @extend_schema(operation_id="listTransfers", parameters=[TransferFilterSerializer])
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Transfers (truck loads, evening returns, moves between cold rooms), newest day first, paginated
        (`limit`, `offset`). Filter by kind, status, location (in or out), days (inclusive) or `search`
        (number, place names)."""
        return super().get(request, *args, **kwargs)

    @extend_schema(
        operation_id="createTransfer", request=TransferWriteSerializer, responses={201: TransferDetailSerializer}
    )
    def post(self, request: Request) -> Response:
        """Prepare a transfer (a draft), or with `validate` also move the stock at once. Its kind comes
        from the places: into a truck is a load, out of one a return. A load line without `unit_price`
        takes the sale price in force. Errors of a line come back on `lines.<index>.<field>`."""
        serializer = TransferWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = _transfer_fields(self.organization, serializer.validated_data)
        transfer = services.create_transfer(organization=self.organization, actor=self.membership.user, **data)
        return _transfer_answer(self.organization, transfer.pk, status_code=status.HTTP_201_CREATED)


class TransferDetailView(TransferView):
    @extend_schema(operation_id="getTransfer", responses=TransferDetailSerializer)
    def get(self, request: Request, transfer_id: int) -> Response:
        """One transfer; once validated, each line lists the batches its kg came from."""
        return _transfer_answer(self.organization, self.transfer(transfer_id).pk)

    @extend_schema(operation_id="updateTransfer", request=TransferWriteSerializer, responses=TransferDetailSerializer)
    def put(self, request: Request, transfer_id: int) -> Response:
        """Change a draft (every line is replaced), and with `validate` move the stock too."""
        transfer = self.transfer(transfer_id)
        serializer = TransferWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = _transfer_fields(self.organization, serializer.validated_data)
        services.update_transfer(transfer=transfer, actor=self.membership.user, **data)
        return _transfer_answer(self.organization, transfer.pk)


class TransferValidateView(TransferView):
    @extend_schema(operation_id="validateTransfer", request=None, responses=TransferDetailSerializer)
    def post(self, request: Request, transfer_id: int) -> Response:
        """Validate a draft: its kg move, oldest batch first. Refused as a whole when the source holds
        too little (on `lines.<index>.quantity`) or for a day still to come."""
        services.validate_transfer(transfer=self.transfer(transfer_id), actor=self.membership.user)
        return _transfer_answer(self.organization, transfer_id)


class TransferCancelView(TransferView):
    @extend_schema(operation_id="cancelTransfer", request=None, responses=TransferDetailSerializer)
    def post(self, request: Request, transfer_id: int) -> Response:
        """Give up a draft. A validated transfer is corrected by a transfer the other way."""
        services.cancel_transfer(transfer=self.transfer(transfer_id), actor=self.membership.user)
        return _transfer_answer(self.organization, transfer_id)


class TruckDayView(OfficeView):
    @extend_schema(operation_id="getTruckDay", parameters=[TruckDayFilterSerializer], responses=TruckDaySerializer)
    def get(self, request: Request) -> Response:
        """A truck's day per product from its validated transfers: kg loaded, kg returned, and loaded −
        returned, sold or lost, with the day's price per kg and what that is worth."""
        filters = TruckDayFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        try:
            location = selectors.location_of(self.organization, filters.validated_data["location"])
        except StockLocation.DoesNotExist:
            raise Http404 from None
        day = filters.validated_data["date"]
        lines = selectors.truck_day(self.organization, location_id=location.pk, day=day)
        total = sum((line.amount for line in lines if line.amount is not None), Decimal("0.000"))
        return Response(TruckDaySerializer({"location": location, "date": day, "lines": lines, "amount": total}).data)
