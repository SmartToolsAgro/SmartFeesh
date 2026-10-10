from django.core.exceptions import ValidationError
from django.http import Http404
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import Membership, Organization
from apps.core.permissions import ReadOfficeWriteOwnerOrManager, membership_of
from apps.inventory import selectors, services
from apps.inventory.models import StockLocation

from .serializers import (
    StockLocationCreateSerializer,
    StockLocationFilterSerializer,
    StockLocationSerializer,
    StockLocationUpdateSerializer,
)


# Base of the location views: rows of the user's organization only (D-022); drivers get 403 and read their
# own truck from `/me`. A comment, not a docstring: a docstring would describe every endpoint in the schema.
class LocationView(APIView):
    permission_classes = (ReadOfficeWriteOwnerOrManager,)

    @property
    def membership(self) -> Membership:
        membership = membership_of(self.request)
        assert membership is not None  # guaranteed by the permission class
        return membership

    @property
    def organization(self) -> Organization:
        return self.membership.organization

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
