from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsMember, membership_of

from .. import selectors, services
from .serializers import MarkReadSerializer, NotificationListSerializer, UnreadSerializer


class MyNotificationsView(APIView):
    """What the office or a driver is told (D-174): both apps ask for it every few seconds."""

    permission_classes = (IsMember,)

    @extend_schema(operation_id="listMyNotifications", responses=NotificationListSerializer)
    def get(self, request: Request) -> Response:
        """The newest notifications of the logged-in person, newest first, and how many they have not read."""
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        answer = {"unread": selectors.unread_count(membership), "results": selectors.latest_for(membership)}
        return Response(NotificationListSerializer(answer).data)


class MyNotificationsReadView(APIView):
    permission_classes = (IsMember,)

    @extend_schema(operation_id="markMyNotificationsRead", request=MarkReadSerializer, responses=UnreadSerializer)
    def post(self, request: Request) -> Response:
        """Some notifications (`ids`), or all of them (`all`), are read by the logged-in person."""
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        serializer = MarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = None if serializer.validated_data["all"] else serializer.validated_data["ids"]
        unread = services.mark_read(membership=membership, ids=ids)
        return Response(UnreadSerializer({"unread": unread}).data)
