from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import Membership, Organization
from apps.core.permissions import membership_of
from apps.fleet import selectors, services
from apps.fleet.models import Truck

from .permissions import OwnTruckOrOffice
from .serializers import TruckFilterSerializer, TruckSerializer, TruckWriteSerializer


# Base of the truck views: rows of the user's organization only (D-022), a driver's own truck only.
# A comment, not a docstring: a docstring would become the description of every endpoint in the schema.
class TruckView(APIView):
    permission_classes = (OwnTruckOrOffice,)

    @property
    def membership(self) -> Membership:
        membership = membership_of(self.request)
        assert membership is not None  # guaranteed by the permission class
        return membership

    @property
    def organization(self) -> Organization:
        return self.membership.organization

    def truck(self, truck_id: int) -> Truck:
        try:
            truck = selectors.truck_of(self.organization, truck_id)
        except Truck.DoesNotExist:
            raise Http404 from None
        self.check_object_permissions(self.request, truck)
        return truck

    def truck_answer(self, truck_id: int, status_code: int = status.HTTP_200_OK) -> Response:
        return Response(TruckSerializer(selectors.truck_of(self.organization, truck_id)).data, status=status_code)


class TruckListView(TruckView):
    @extend_schema(operation_id="listTrucks", parameters=[TruckFilterSerializer], responses=TruckSerializer(many=True))
    def get(self, request: Request) -> Response:
        """Trucks sorted by name, with their driver. A driver sees only their own truck."""
        filters = TruckFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        trucks = selectors.trucks_of(self.organization, status=filters.validated_data["status"])
        if self.membership.role not in selectors.OFFICE_ROLES:
            own = selectors.truck_of_driver(self.membership)
            trucks = trucks.filter(pk=own.pk) if own else trucks.none()
        return Response(TruckSerializer(trucks, many=True).data)

    @extend_schema(operation_id="createTruck", request=TruckWriteSerializer, responses={201: TruckSerializer})
    def post(self, request: Request) -> Response:
        """A new truck, with the stock location that holds its goods."""
        serializer = TruckWriteSerializer(data=request.data, context={"organization": self.organization})
        serializer.is_valid(raise_exception=True)
        truck = services.create_truck(
            organization=self.organization, actor=self.membership.user, **serializer.validated_data
        )
        return self.truck_answer(truck.pk, status.HTTP_201_CREATED)


class TruckDetailView(TruckView):
    @extend_schema(operation_id="getTruck", responses=TruckSerializer)
    def get(self, request: Request, truck_id: int) -> Response:
        return Response(TruckSerializer(self.truck(truck_id)).data)

    @extend_schema(operation_id="updateTruck", request=TruckWriteSerializer, responses=TruckSerializer)
    def patch(self, request: Request, truck_id: int) -> Response:
        """Rename a truck, change its plate or its driver (`driver: null` takes it back from its driver)."""
        truck = self.truck(truck_id)
        serializer = TruckWriteSerializer(data=request.data, partial=True, context={"organization": self.organization})
        serializer.is_valid(raise_exception=True)
        services.update_truck(truck=truck, actor=self.membership.user, **serializer.validated_data)
        return self.truck_answer(truck_id)


class TruckArchiveView(TruckView):
    @extend_schema(operation_id="archiveTruck", request=None, responses=TruckSerializer)
    def post(self, request: Request, truck_id: int) -> Response:
        """An archived truck keeps its history, receives no more stock and has no driver."""
        services.set_truck_active(truck=self.truck(truck_id), actor=self.membership.user, is_active=False)
        return self.truck_answer(truck_id)


class TruckRestoreView(TruckView):
    @extend_schema(operation_id="restoreTruck", request=None, responses=TruckSerializer)
    def post(self, request: Request, truck_id: int) -> Response:
        services.set_truck_active(truck=self.truck(truck_id), actor=self.membership.user, is_active=True)
        return self.truck_answer(truck_id)
