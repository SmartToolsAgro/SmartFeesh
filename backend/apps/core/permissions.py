"""Role checks for the API layer (ARCHITECTURE §4.8). Hiding a button is not security: every view sets one."""

from typing import ClassVar

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from .models import Membership, Role, User
from .selectors import active_membership

_CACHE_ATTRIBUTE = "_frutti_membership"


def membership_of(request: Request) -> Membership | None:
    """The logged-in user's active membership, looked up once per request."""
    if not isinstance(request.user, User):
        return None
    if not hasattr(request, _CACHE_ATTRIBUTE):
        setattr(request, _CACHE_ATTRIBUTE, active_membership(request.user))
    membership: Membership | None = getattr(request, _CACHE_ATTRIBUTE)
    return membership


class HasRole(BasePermission):
    """Base class: allowed when the user's role in their organization is one of `roles`."""

    roles: ClassVar[frozenset[Role]] = frozenset(Role)

    def has_permission(self, request: Request, view: APIView) -> bool:
        membership = membership_of(request)
        return membership is not None and membership.role in self.roles


class IsMember(HasRole):
    """Any role, as long as the user belongs to an active organization."""


class IsOwnerOrManager(HasRole):
    roles = frozenset({Role.OWNER, Role.MANAGER})


class IsDriver(HasRole):
    roles = frozenset({Role.DRIVER})


class ReadMemberWriteOwnerOrManager(HasRole):
    """Every member may read (drivers need the catalogue to sell); only owners and managers may change."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        membership = membership_of(request)
        if membership is None:
            return False
        if request.method in SAFE_METHODS:
            return True
        return membership.role in IsOwnerOrManager.roles


class ReadOwnerOrAccountantWriteOwner(HasRole):
    """The owner's own money (lot results, partners' shares and capital, D-060, D-061): the owner reads and
    changes, the accountant reads; managers and drivers get 403."""

    roles = frozenset({Role.OWNER, Role.ACCOUNTANT})

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS:
            return True
        membership = membership_of(request)
        return membership is not None and membership.role == Role.OWNER


class ReadOfficeWriteOwnerOrManager(HasRole):
    """Office data drivers have no use for (suppliers, purchases): owners, managers and the accountant read;
    only owners and managers change."""

    roles = frozenset({Role.OWNER, Role.MANAGER, Role.ACCOUNTANT})

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS:
            return True
        membership = membership_of(request)
        return membership is not None and membership.role in IsOwnerOrManager.roles
