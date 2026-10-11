from rest_framework.permissions import SAFE_METHODS
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.core.models import Role
from apps.core.permissions import HasRole, membership_of


class ReadOwnerOrAccountantWriteOwner(HasRole):
    """Pay is the most private data of the company (D-055): the owner reads and writes, the accountant reads.
    Managers and drivers get 403 on everything: nobody sees another person's pay."""

    roles = frozenset({Role.OWNER, Role.ACCOUNTANT})

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS:
            return True
        membership = membership_of(request)
        return membership is not None and membership.role == Role.OWNER
