from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.models import AuditLog, Role
from apps.core.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.inventory import selectors, services
from apps.inventory.models import LocationKind

from .factories import StockLocationFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def organization():
    return OrganizationFactory.create()


@pytest.fixture
def actor():
    return UserFactory.create()


def new_location(organization, actor, **fields):
    values: dict[str, Any] = {"kind": LocationKind.COLD_ROOM, "name": "Chambre froide 1"}
    values.update(fields)
    return services.create_location(organization=organization, actor=actor, **values)


# ---- services ----


def test_a_cold_room_sells_only_when_it_has_counter_sales(organization, actor):
    room = new_location(organization, actor, counter_sales=True)
    store = new_location(organization, actor, kind=LocationKind.OTHER, name="Congélateur marché")

    assert (room.sells, store.sells) == (True, False)
    assert AuditLog.objects.filter(action="location.created").count() == 2


def test_names_are_unique_per_organization_whatever_the_case(organization, actor):
    new_location(organization, actor)

    with pytest.raises(ValidationError) as caught:
        new_location(organization, actor, name=" chambre froide 1 ")
    assert list(caught.value.message_dict) == ["name"]

    assert new_location(OrganizationFactory.create(), actor).pk is not None


def test_an_unknown_kind_and_an_empty_name_are_refused(organization, actor):
    with pytest.raises(ValidationError) as caught:
        new_location(organization, actor, kind="boat", name=" ")

    assert set(caught.value.message_dict) == {"kind", "name"}


def test_a_truck_location_never_has_counter_sales(organization, actor):
    truck = new_location(organization, actor, kind=LocationKind.TRUCK, name="Camion 1", counter_sales=True)

    assert truck.counter_sales is False
    assert truck.sells is True


def test_an_update_audits_only_what_changed(organization, actor):
    room = new_location(organization, actor)

    services.update_location(location=room, actor=actor, counter_sales=True)
    services.update_location(location=room, actor=actor, name="Chambre froide 1")

    entry = AuditLog.objects.get(action="location.updated")
    assert (entry.before, entry.after) == ({"counter_sales": False}, {"counter_sales": True})


def test_the_list_puts_cold_rooms_first_and_hides_archived_ones(organization, actor):
    truck = StockLocationFactory.create(organization=organization, kind=LocationKind.TRUCK, name="A camion")
    room = StockLocationFactory.create(organization=organization, name="Z chambre")
    archived = StockLocationFactory.create(organization=organization, name="Ancienne", is_active=False)

    assert list(selectors.locations_of(organization)) == [room, truck]
    assert list(selectors.locations_of(organization, status="archived")) == [archived]
    assert list(selectors.locations_of(organization, kinds=["truck"])) == [truck]


# ---- API ----


def client_for(role, organization=None):
    membership = MembershipFactory.create(role=role, organization=organization or OrganizationFactory.create())
    client = APIClient()
    client.force_authenticate(membership.user)
    return client, membership


def test_the_owner_creates_renames_and_archives_a_cold_room():
    client, _ = client_for(Role.OWNER)

    created = client.post(
        reverse("location-list"), {"kind": "cold_room", "name": "Chambre froide 1", "counter_sales": True}
    )
    assert created.status_code == 201
    body = created.json()
    assert (body["kind"], body["sells"], body["is_active"]) == ("cold_room", True, True)

    renamed = client.patch(reverse("location-detail", args=[body["id"]]), {"name": "Frigo frais"}, format="json")
    assert renamed.json()["name"] == "Frigo frais"
    assert renamed.json()["counter_sales"] is True

    archived = client.post(reverse("location-archive", args=[body["id"]]))
    assert archived.json()["is_active"] is False
    assert client.get(reverse("location-list")).json() == []
    assert client.post(reverse("location-restore", args=[body["id"]])).json()["is_active"] is True


def test_a_truck_location_is_neither_created_nor_changed_here():
    client, owner = client_for(Role.OWNER)
    truck = StockLocationFactory.create(organization=owner.organization, kind=LocationKind.TRUCK, name="Camion 1")

    assert client.post(reverse("location-list"), {"kind": "truck", "name": "Camion 9"}).status_code == 400
    assert client.patch(reverse("location-detail", args=[truck.pk]), {"name": "X"}, format="json").status_code == 400
    assert client.post(reverse("location-archive", args=[truck.pk])).status_code == 400
    # It is still listed with the others, for the stock screens.
    assert [row["kind"] for row in client.get(reverse("location-list")).json()] == ["truck"]


@pytest.mark.parametrize(
    ("role", "read_status", "write_status"),
    [(Role.MANAGER, 200, 201), (Role.ACCOUNTANT, 200, 403), (Role.DRIVER, 403, 403)],
)
def test_only_the_office_reads_locations_and_only_owners_and_managers_change_them(role, read_status, write_status):
    client, _ = client_for(role)

    assert client.get(reverse("location-list")).status_code == read_status
    assert client.post(reverse("location-list"), {"kind": "other", "name": "Stand"}).status_code == write_status


def test_another_organization_locations_are_invisible():
    client, _ = client_for(Role.OWNER)
    other = StockLocationFactory.create()

    assert client.get(reverse("location-list")).json() == []
    assert client.get(reverse("location-detail", args=[other.pk])).status_code == 404
    assert client.post(reverse("location-archive", args=[other.pk])).status_code == 404
