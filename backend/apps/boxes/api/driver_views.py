"""Returnable boxes on the driver's phone (P1-T14d, D-122): the truck of the day only, never another's."""

from typing import TYPE_CHECKING, Any

from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.utils import timezone
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.boxes import selectors, services
from apps.boxes.services import checked_box_counts
from apps.core.models import Membership
from apps.core.permissions import IsDriver, membership_of
from apps.dayclose import selectors as dayclose
from apps.fleet import selectors as fleet
from apps.partners import selectors as partners

from .driver_serializers import MyBoxDaySerializer, MyBoxPickupWriteSerializer

if TYPE_CHECKING:
    from apps.fleet.models import Truck


def _day_answer(membership: Membership, truck: "Truck") -> dict[str, Any]:
    """Today's boxes of the driver's truck, per box type."""
    day = timezone.localdate()
    return {
        "date": day,
        "truck_name": truck.location.name,
        "lines": selectors.truck_day(membership.organization, truck.location, day),
    }


class MyBoxDayView(APIView):
    permission_classes = (IsDriver,)

    @extend_schema(operation_id="getMyBoxDay", responses=MyBoxDaySerializer)
    def get(self, request: Request) -> Response:
        """Today's boxes on the driver's truck, per box type: loaded, left with clients and collected back today,
        and the expected count on the truck (the real ledger balance, all days). 404 without a truck of the day."""
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        truck = fleet.truck_of_driver(membership)
        if truck is None:
            raise Http404
        return Response(MyBoxDaySerializer(_day_answer(membership, truck)).data)


class MyBoxPickupView(APIView):
    permission_classes = (IsDriver,)

    @extend_schema(
        operation_id="collectMyBoxes",
        request=MyBoxPickupWriteSerializer,
        responses={201: MyBoxDaySerializer},
    )
    def post(self, request: Request) -> Response:
        """Boxes a client hands back to the driver's truck today, per box type. Refused as a whole when the
        client holds fewer boxes of one type than asked, or when the driver's day is approved. A `client_uuid`
        already used returns the day as it is after that pickup (the driver app retries)."""
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        truck = fleet.truck_of_driver(membership)
        if truck is None:
            raise exceptions.ValidationError(_("Choisissez d'abord votre camion."))
        dayclose.refuse_if_day_approved(membership)
        serializer = MyBoxPickupWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        errors: dict[str, str] = {}
        counts = checked_box_counts(serializer.validated_data["boxes"], errors, prefix="boxes")
        if errors:
            raise exceptions.ValidationError(errors)
        if not counts:
            raise exceptions.ValidationError({"boxes": _("Indiquez au moins une caisse.")})
        try:
            customer = partners.customer_of(membership.organization, serializer.validated_data["customer"])
        except ObjectDoesNotExist:
            raise exceptions.ValidationError({"customer": _("Client inconnu.")}) from None
        services.post_pickup(
            organization=membership.organization,
            actor=membership.user,
            customer=customer,
            location=truck.location,
            counts=counts,
            client_uuid=serializer.validated_data["client_uuid"],
        )
        return Response(MyBoxDaySerializer(_day_answer(membership, truck)).data, status=status.HTTP_201_CREATED)
