from django.contrib.auth import authenticate, login, logout
from django.db import connection
from django.db.models import QuerySet
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import selectors, services
from apps.core.authentication import LoginIPThrottle, LoginUsernameThrottle
from apps.core.models import Membership, User
from apps.core.permissions import IsMember, IsOwnerOrManager, membership_of

from .serializers import LanguageSerializer, LoginSerializer, MemberSerializer, SessionSerializer


@extend_schema(
    responses=inline_serializer(
        "Health",
        fields={"status": serializers.CharField(), "database": serializers.CharField()},
    ),
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    """Liveness + database check, used by Docker, the load balancer and uptime monitoring."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        database = "ok"
    except Exception:  # noqa: BLE001 - any DB failure means "down"
        database = "unavailable"
    status_code = 200 if database == "ok" else 503
    return Response({"status": "ok" if status_code == 200 else "degraded", "database": database}, status=status_code)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Sets the CSRF cookie. The apps call it once before the first POST (D-008)."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(request=None, responses={204: None})
    def get(self, request: Request) -> Response:
        return Response(status=status.HTTP_204_NO_CONTENT)


# DRF only checks CSRF for a logged-in session, so the login form is protected here explicitly.
@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = (LoginIPThrottle, LoginUsernameThrottle)

    def get_authenticate_header(self, request: Request) -> str:
        # Without it DRF turns the 401 of a wrong password into a 403.
        return "Session"

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: SessionSerializer,
            401: OpenApiResponse(description="Wrong username or password"),
            403: OpenApiResponse(description="The account has no active role in an organization"),
            429: OpenApiResponse(description="Too many attempts"),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request, **serializer.validated_data)
        if not isinstance(user, User):
            # Same answer for an unknown user, a wrong password and a disabled account.
            raise AuthenticationFailed(_("Identifiant ou mot de passe incorrect."))
        membership = selectors.active_membership(user)
        if membership is None:
            raise PermissionDenied(_("Ce compte n'est rattaché à aucune société active."))
        login(request, user)
        return Response(SessionSerializer(membership).data)


class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request) -> Response:
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """The logged-in user, their organization and their role."""

    permission_classes = (IsMember,)

    @extend_schema(responses=SessionSerializer)
    def get(self, request: Request) -> Response:
        return Response(SessionSerializer(membership_of(request)).data)

    @extend_schema(request=LanguageSerializer, responses=SessionSerializer)
    def patch(self, request: Request) -> Response:
        """Change the language of the apps for the logged-in user."""
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        serializer = LanguageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.set_language(user=membership.user, language=serializer.validated_data["language"])
        return Response(SessionSerializer(membership).data)


class MemberListView(ListAPIView[Membership]):
    """Users of the organization and their roles. Owners and managers only."""

    permission_classes = (IsOwnerOrManager,)
    serializer_class = MemberSerializer
    pagination_class = None

    def get_queryset(self) -> QuerySet[Membership]:
        membership = membership_of(self.request)
        assert membership is not None  # guaranteed by the permission class
        return selectors.members_of(membership.organization)
