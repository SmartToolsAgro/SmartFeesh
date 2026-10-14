from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.db import connection
from django.db.models import QuerySet
from django.http import FileResponse, Http404
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import selectors, services
from apps.core.authentication import LoginIPThrottle, LoginUsernameThrottle, PasswordChangeThrottle
from apps.core.models import Membership, Organization, User
from apps.core.permissions import IsMember, IsOwner, ReadOfficeWriteOwnerOrManager, membership_of

from .serializers import (
    ChangePasswordSerializer,
    LanguageSerializer,
    LoginSerializer,
    MemberCreateSerializer,
    MemberPasswordResetSerializer,
    MemberRoleSerializer,
    MemberSerializer,
    OrganizationSerializer,
    ProfilePhotoUploadSerializer,
    SessionSerializer,
    UpdateProfileSerializer,
)


@extend_schema(
    operation_id="getHealth",
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

    @extend_schema(operation_id="getCsrfCookie", request=None, responses={204: None})
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
        operation_id="login",
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

    @extend_schema(operation_id="logout", request=None, responses={204: None})
    def post(self, request: Request) -> Response:
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """The logged-in user, their organization and their role."""

    permission_classes = (IsMember,)

    @extend_schema(operation_id="getSession", responses=SessionSerializer)
    def get(self, request: Request) -> Response:
        return Response(SessionSerializer(membership_of(request)).data)

    @extend_schema(operation_id="setLanguage", request=LanguageSerializer, responses=SessionSerializer)
    def patch(self, request: Request) -> Response:
        """Change the language of the apps for the logged-in user."""
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        serializer = LanguageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.set_language(user=membership.user, language=serializer.validated_data["language"])
        return Response(SessionSerializer(membership).data)


# ---- Self-service profile (any logged-in user, D-123) ----


class MyProfileView(APIView):
    """A user's own display name, changed from their profile menu (not their role: only the owner sets that)."""

    permission_classes = (IsMember,)

    @extend_schema(operation_id="updateMyProfile", request=UpdateProfileSerializer, responses=SessionSerializer)
    def patch(self, request: Request) -> Response:
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        serializer = UpdateProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership.user = services.update_own_profile(user=membership.user, **serializer.validated_data)
        return Response(SessionSerializer(membership).data)


class MyPasswordView(APIView):
    """A user changes their own password; the old one proves it is really them (no email reset exists, D-123)."""

    permission_classes = (IsMember,)
    throttle_classes = (PasswordChangeThrottle,)

    @extend_schema(operation_id="changeMyPassword", request=ChangePasswordSerializer, responses={204: None})
    def post(self, request: Request) -> Response:
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.change_own_password(user=membership.user, **serializer.validated_data)
        update_session_auth_hash(request, membership.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyAvatarView(APIView):
    """A user's own photo, shown in the topbar. Nobody but the user themselves may change it (D-123)."""

    permission_classes = (IsMember,)
    parser_classes = (MultiPartParser,)

    @extend_schema(
        operation_id="uploadMyAvatar",
        request={"multipart/form-data": ProfilePhotoUploadSerializer},
        responses={200: SessionSerializer, 400: OpenApiResponse(description="Not a readable JPEG, PNG or WebP")},
    )
    def put(self, request: Request) -> Response:
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        serializer = ProfilePhotoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership.user = services.set_user_avatar(user=membership.user, upload=serializer.validated_data["photo"])
        return Response(SessionSerializer(membership).data)

    @extend_schema(operation_id="removeMyAvatar", request=None, responses=SessionSerializer)
    def delete(self, request: Request) -> Response:
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        membership.user = services.remove_user_avatar(user=membership.user)
        return Response(SessionSerializer(membership).data)


class UserAvatarView(APIView):
    """A member's photo, read by an <img> tag. Visible only to someone sharing the same organization."""

    permission_classes = (IsMember,)

    # Read by an <img> tag, not by the generated client: kept out of the API contract.
    @extend_schema(exclude=True)
    def get(self, request: Request, user_id: int) -> FileResponse:
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        target = selectors.members_of(membership.organization).filter(user_id=user_id).first()
        if target is None or not target.user.avatar:
            raise Http404
        response = FileResponse(target.user.avatar.open("rb"), content_type="image/webp")
        # The address changes with every new photo (see UserSerializer.get_avatar_url).
        response["Cache-Control"] = "private, max-age=31536000, immutable"
        return response


# ---- Company profile: the logo (owner request, D-123) ----


class OrganizationLogoView(APIView):
    """The company logo on the Paramètres page. Owners and managers may change it (same as the legal fields)."""

    permission_classes = (ReadOfficeWriteOwnerOrManager,)
    parser_classes = (MultiPartParser,)

    # Read by an <img> tag, not by the generated client: kept out of the API contract.
    @extend_schema(exclude=True)
    def get(self, request: Request, organization_id: int) -> FileResponse:
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        if membership.organization_id != organization_id:
            raise Http404
        organization = membership.organization
        if not organization.logo:
            raise Http404
        response = FileResponse(organization.logo.open("rb"), content_type="image/webp")
        # The address changes with every new logo (see OrganizationSerializer.get_logo_url).
        response["Cache-Control"] = "private, max-age=31536000, immutable"
        return response

    @extend_schema(
        operation_id="uploadOrganizationLogo",
        request={"multipart/form-data": ProfilePhotoUploadSerializer},
        responses={200: OrganizationSerializer, 400: OpenApiResponse(description="Not a readable JPEG, PNG or WebP")},
    )
    def put(self, request: Request, organization_id: int) -> Response:
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        if membership.organization_id != organization_id:
            raise Http404
        serializer = ProfilePhotoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = services.set_organization_logo(
            organization=membership.organization, actor=membership.user, upload=serializer.validated_data["photo"]
        )
        return Response(OrganizationSerializer(organization).data)

    @extend_schema(operation_id="removeOrganizationLogo", request=None, responses=OrganizationSerializer)
    def delete(self, request: Request, organization_id: int) -> Response:
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        if membership.organization_id != organization_id:
            raise Http404
        organization = services.remove_organization_logo(organization=membership.organization, actor=membership.user)
        return Response(OrganizationSerializer(organization).data)


# ---- Users management: owner only (D-123) ----


def _member_or_404(organization: Organization, member_id: int) -> Membership:
    member = selectors.members_of(organization).filter(pk=member_id).first()
    if member is None:
        raise Http404
    return member


@extend_schema_view(get=extend_schema(operation_id="listMembers"))
class MemberListView(ListAPIView[Membership]):
    """Users of the organization and their roles, and adding a new one. Owner only (D-123)."""

    permission_classes = (IsOwner,)
    serializer_class = MemberSerializer
    pagination_class = None

    def get_queryset(self) -> QuerySet[Membership]:
        membership = membership_of(self.request)
        assert membership is not None  # guaranteed by the permission class
        return selectors.members_of(membership.organization)

    @extend_schema(operation_id="createMember", request=MemberCreateSerializer, responses={201: MemberSerializer})
    def post(self, request: Request) -> Response:
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        serializer = MemberCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = services.create_member(
            organization=membership.organization, actor=membership.user, **serializer.validated_data
        )
        return Response(MemberSerializer(created).data, status=status.HTTP_201_CREATED)


class MemberRoleView(APIView):
    permission_classes = (IsOwner,)

    @extend_schema(operation_id="setMemberRole", request=MemberRoleSerializer, responses=MemberSerializer)
    def patch(self, request: Request, member_id: int) -> Response:
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        target = _member_or_404(membership.organization, member_id)
        serializer = MemberRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.set_member_role(
            organization=membership.organization, membership=target, actor=membership.user, **serializer.validated_data
        )
        return Response(MemberSerializer(updated).data)


class MemberDeactivateView(APIView):
    permission_classes = (IsOwner,)

    @extend_schema(operation_id="deactivateMember", request=None, responses=MemberSerializer)
    def post(self, request: Request, member_id: int) -> Response:
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        target = _member_or_404(membership.organization, member_id)
        updated = services.set_member_active(
            organization=membership.organization, membership=target, actor=membership.user, is_active=False
        )
        return Response(MemberSerializer(updated).data)


class MemberReactivateView(APIView):
    permission_classes = (IsOwner,)

    @extend_schema(operation_id="reactivateMember", request=None, responses=MemberSerializer)
    def post(self, request: Request, member_id: int) -> Response:
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        target = _member_or_404(membership.organization, member_id)
        updated = services.set_member_active(
            organization=membership.organization, membership=target, actor=membership.user, is_active=True
        )
        return Response(MemberSerializer(updated).data)


class MemberPasswordResetView(APIView):
    """The owner types a new password for someone else (shown once); no email or SMS reset exists (D-123)."""

    permission_classes = (IsOwner,)

    @extend_schema(operation_id="resetMemberPassword", request=MemberPasswordResetSerializer, responses={204: None})
    def post(self, request: Request, member_id: int) -> Response:
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        target = _member_or_404(membership.organization, member_id)
        serializer = MemberPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.reset_member_password(
            organization=membership.organization, membership=target, actor=membership.user, **serializer.validated_data
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
