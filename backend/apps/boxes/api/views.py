from django.db.models import QuerySet
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.boxes import selectors
from apps.boxes.models import BoxHolder, BoxMovement
from apps.core.api.pagination import PagedList
from apps.core.models import Membership, Organization
from apps.core.permissions import ReadOfficeWriteOwnerOrManager, membership_of

from .serializers import BoxBalanceSerializer, BoxMovementFilterSerializer, BoxMovementSerializer


# Office reads only (owners, managers, accountant): drivers get 403 (D-023). Rows come from the user's
# organization only (D-022). A comment, not a docstring: a docstring would describe every endpoint.
class BoxOfficeView(APIView):
    permission_classes = (ReadOfficeWriteOwnerOrManager,)

    @property
    def membership(self) -> Membership:
        membership = membership_of(self.request)
        assert membership is not None  # guaranteed by the permission class
        return membership

    @property
    def organization(self) -> Organization:
        return self.membership.organization


class BoxBalanceListView(BoxOfficeView):
    @extend_schema(operation_id="listBoxBalances", responses=BoxBalanceSerializer(many=True))
    def get(self, request: Request) -> Response:
        """How many boxes each holder has, per box type: locations, clients and suppliers that have moved
        boxes. A supplier's count is what we owe it (boxes it lent us)."""
        return Response(BoxBalanceSerializer(selectors.balances_of(self.organization), many=True).data)


class BoxMovementListView(BoxOfficeView, ListAPIView[BoxMovement]):
    serializer_class = BoxMovementSerializer
    pagination_class = PagedList

    def get_queryset(self) -> QuerySet[BoxMovement]:
        filters = BoxMovementFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        holder = None
        if filters.validated_data.get("holder") is not None:
            try:
                holder = BoxHolder.objects.for_organization(self.organization).get(pk=filters.validated_data["holder"])
            except BoxHolder.DoesNotExist:
                raise Http404 from None
        return selectors.movements_of(self.organization, box_type=filters.validated_data.get("box_type"), holder=holder)

    @extend_schema(operation_id="listBoxMovements", parameters=[BoxMovementFilterSerializer])
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        """The box history, newest first, paginated (`limit`, `offset`). Filter by one holder (either side
        of the movement) and by box type."""
        return super().get(request, *args, **kwargs)
