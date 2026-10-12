from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import Membership
from apps.core.permissions import IsDriver, ReadOfficeWriteOwnerOrManager, membership_of
from apps.dayclose import selectors, services
from apps.dayclose.models import DayClosing
from apps.fleet import selectors as fleet

from .serializers import (
    DayClosingDetailSerializer,
    DayClosingFilterSerializer,
    DayClosingRowSerializer,
    DayClosingWriteSerializer,
    JustificationSerializer,
    MyDaySummarySerializer,
)


def _my_day_answer(membership: Membership) -> dict[str, object]:
    driver_day = fleet.driver_day_of(membership)
    if driver_day is None:
        raise Http404
    return {
        "summary": selectors.day_summary(membership.organization, driver_day),
        "closing": selectors.closing_of(driver_day),
    }


class MyDaySummaryView(APIView):
    permission_classes = (IsDriver,)

    @extend_schema(operation_id="getMyDaySummary", responses=MyDaySummarySerializer)
    def get(self, request: Request) -> Response:
        """The driver's day so far: sales, cash, expenses and the stock per product, and the closing if sent.
        404 until the day is started."""
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        return Response(MyDaySummarySerializer(_my_day_answer(membership)).data)


class MyDayClosingView(APIView):
    permission_classes = (IsDriver,)

    @extend_schema(
        operation_id="closeMyDay", request=DayClosingWriteSerializer, responses={201: MyDaySummarySerializer}
    )
    def post(self, request: Request) -> Response:
        """Send the end of the day with the cash counted and an optional note. Sent again only after the office
        asked for a justification."""
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        serializer = DayClosingWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        driver_day = fleet.driver_day_of(membership)
        if driver_day is None:
            raise Http404
        services.submit_day_closing(
            driver_day=driver_day,
            actor=membership.user,
            counted_cash=serializer.validated_data["counted_cash"],
            note=serializer.validated_data["note"],
        )
        return Response(MyDaySummarySerializer(_my_day_answer(membership)).data, status=status.HTTP_201_CREATED)


# Base of the office views: rows of the user's organization only. Owner and manager decide, the accountant reads.
class DayClosingView(APIView):
    permission_classes = (ReadOfficeWriteOwnerOrManager,)

    @property
    def membership(self) -> Membership:
        membership = membership_of(self.request)
        assert membership is not None  # guaranteed by the permission class
        return membership

    def closing(self, closing_id: int) -> DayClosing:
        try:
            return selectors.closing_by_id(self.membership.organization, closing_id)
        except ObjectDoesNotExist:
            raise Http404 from None

    def answer(self, closing_id: int) -> Response:
        return Response(DayClosingDetailSerializer(self.closing(closing_id)).data)


class DayClosingListView(DayClosingView):
    @extend_schema(
        operation_id="listDayClosings",
        parameters=[DayClosingFilterSerializer],
        responses=DayClosingRowSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        """Days sent by the drivers, newest first. Filter by status."""
        filters = DayClosingFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        rows = selectors.closings_of(self.membership.organization, status=filters.validated_data.get("status"))
        return Response(DayClosingRowSerializer(rows[:100], many=True).data)


class DayClosingDetailView(DayClosingView):
    @extend_schema(operation_id="getDayClosing", responses=DayClosingDetailSerializer)
    def get(self, request: Request, closing_id: int) -> Response:
        """One day with its figures as the driver sent them."""
        return self.answer(closing_id)


class DayClosingApproveView(DayClosingView):
    @extend_schema(operation_id="approveDayClosing", request=None, responses=DayClosingDetailSerializer)
    def post(self, request: Request, closing_id: int) -> Response:
        """Approve the day (owner or manager): it is locked."""
        services.approve_day_closing(closing=self.closing(closing_id), actor=self.membership.user)
        return self.answer(closing_id)


class DayClosingJustificationView(DayClosingView):
    @extend_schema(
        operation_id="requestDayJustification", request=JustificationSerializer, responses=DayClosingDetailSerializer
    )
    def post(self, request: Request, closing_id: int) -> Response:
        """Ask the driver to explain, saying what; they send the day again with a note."""
        serializer = JustificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.request_justification(
            closing=self.closing(closing_id), actor=self.membership.user, reason=serializer.validated_data["reason"]
        )
        return self.answer(closing_id)
