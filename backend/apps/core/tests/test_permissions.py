import pytest
from django.core.cache import cache
from django.urls import path, reverse
from rest_framework.response import Response
from rest_framework.test import APIClient
from rest_framework.views import APIView

from apps.core.models import Role
from apps.core.permissions import IsDriver, IsOwnerOrManager

from .factories import MembershipFactory, OrganizationFactory, UserFactory

pytestmark = pytest.mark.django_db


class AdminOnlyView(APIView):
    permission_classes = (IsOwnerOrManager,)

    def get(self, request):
        return Response({"area": "admin"})


class DriverOnlyView(APIView):
    permission_classes = (IsDriver,)

    def get(self, request):
        return Response({"area": "truck"})


urlpatterns = [
    path("admin-only", AdminOnlyView.as_view()),
    path("driver-only", DriverOnlyView.as_view()),
]


@pytest.fixture(autouse=True)
def _reset_throttles():
    cache.clear()


def client_for(role, organization=None, **membership_fields):
    membership = MembershipFactory.create(
        role=role,
        organization=organization or OrganizationFactory.create(),
        user=UserFactory.create(),
        **membership_fields,
    )
    client = APIClient()
    client.force_authenticate(membership.user)
    return client, membership


@pytest.mark.urls(__name__)
@pytest.mark.parametrize(
    ("role", "admin_status", "driver_status"),
    [
        (Role.OWNER, 200, 403),
        (Role.MANAGER, 200, 403),
        (Role.DRIVER, 403, 200),
        (Role.ACCOUNTANT, 403, 403),
    ],
)
def test_each_role_only_reaches_its_own_area(role, admin_status, driver_status):
    client, _ = client_for(role)

    assert client.get("/admin-only").status_code == admin_status
    assert client.get("/driver-only").status_code == driver_status


@pytest.mark.urls(__name__)
def test_anonymous_visitors_get_401_and_inactive_members_get_403():
    assert APIClient().get("/admin-only").status_code == 401

    client, _ = client_for(Role.OWNER, is_active=False)
    assert client.get("/admin-only").status_code == 403


def test_a_driver_gets_403_on_the_member_list():
    client, _ = client_for(Role.DRIVER)

    assert client.get(reverse("member-list")).status_code == 403


def test_the_member_list_only_shows_the_owner_s_own_organization():
    client, owner = client_for(Role.OWNER)
    colleague = MembershipFactory.create(organization=owner.organization, role=Role.DRIVER)
    MembershipFactory.create(role=Role.DRIVER)  # another company's driver

    response = client.get(reverse("member-list"))

    assert response.status_code == 200
    assert {row["user"]["username"] for row in response.json()} == {owner.user.username, colleague.user.username}
    assert {row["role"] for row in response.json()} == {"owner", "driver"}
