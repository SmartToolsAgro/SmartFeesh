from typing import Any

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.core.permissions import IsOwnerOrManager, membership_of
from apps.fleet import selectors


class OwnTruckOrOffice(BasePermission):
    """Every member reads trucks, but a driver only their own one; owners and managers change them.

    Views call `check_object_permissions` on the truck they act on, and filter lists the same way.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        membership = membership_of(request)
        if membership is None:
            return False
        return request.method in SAFE_METHODS or membership.role in IsOwnerOrManager.roles

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        membership = membership_of(request)
        return membership is not None and selectors.may_use_truck(membership, obj)
