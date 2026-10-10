from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.models import AuditLog, Role
from apps.core.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.fleet import selectors, services
from apps.inventory.tests.factories import StockLocationFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def organization():
    return OrganizationFactory.create()


@pytest.fixture
def actor():
    return UserFactory.create()


def driver_of(organization, **fields):
    return MembershipFactory.create(organization=organization, role=Role.DRIVER, **fields)


def new_truck(organization, actor, **fields):
    values: dict[str, Any] = {"name": "Camion 1", "plate": "101 TU 2001"}
    values.update(fields)
    return services.create_truck(organization=organization, actor=actor, **values)


# ---- services ----


def test_a_truck_gets_its_own_selling_location(organization, actor):
    truck = new_truck(organization, actor, plate=" 101  tu 2001 ")

    assert truck.plate == "101 TU 2001"
    assert (truck.location.kind, truck.location.name, truck.location.sells) == ("truck", "Camion 1", True)
    assert truck.location.organization == organization
    assert set(AuditLog.objects.values_list("action", flat=True)) == {"location.created", "truck.created"}


def test_plates_and_names_are_unique_per_organization(organization, actor):
    new_truck(organization, actor)

    with pytest.raises(ValidationError) as caught:
        new_truck(organization, actor, name="Camion 2", plate="101 tu 2001")
    assert list(caught.value.message_dict) == ["plate"]
    with pytest.raises(ValidationError) as caught:
        new_truck(organization, actor, plate="102 TU 2002")
    assert list(caught.value.message_dict) == ["name"]

    assert new_truck(OrganizationFactory.create(), actor).pk is not None


def test_only_a_driver_of_the_company_can_get_a_truck_and_only_one(organization, actor):
    driver = driver_of(organization)
    manager = MembershipFactory.create(organization=organization, role=Role.MANAGER)
    stranger = driver_of(OrganizationFactory.create())
    new_truck(organization, actor, driver=driver.user)

    for user, message in [
        (manager.user, "pas un chauffeur"),
        (stranger.user, "pas un chauffeur"),
        (driver.user, "déjà"),
    ]:
        with pytest.raises(ValidationError, match=message):
            new_truck(organization, actor, name="Camion 2", plate="102 TU 2002", driver=user)


def test_a_truck_changes_driver_and_name_with_one_audit_entry(organization, actor):
    first, second = driver_of(organization), driver_of(organization)
    truck = new_truck(organization, actor, driver=first.user)

    services.update_truck(truck=truck, actor=actor, name="Camion Mahrès", driver=second.user)

    truck.refresh_from_db()
    assert (truck.location.name, truck.driver) == ("Camion Mahrès", second.user)
    entry = AuditLog.objects.get(action="truck.updated")
    assert entry.before == {"name": "Camion 1", "driver": first.user.username}
    assert entry.after == {"name": "Camion Mahrès", "driver": second.user.username}


def test_leaving_out_the_driver_keeps_it_and_none_takes_the_truck_back(organization, actor):
    driver = driver_of(organization)
    truck = new_truck(organization, actor, driver=driver.user)

    services.update_truck(truck=truck, actor=actor, plate="999 TU 9999")
    truck.refresh_from_db()
    assert truck.driver == driver.user

    services.update_truck(truck=truck, actor=actor, driver=None)
    truck.refresh_from_db()
    assert truck.driver is None


def test_archiving_a_truck_frees_its_driver_and_archives_its_location(organization, actor):
    driver = driver_of(organization)
    truck = new_truck(organization, actor, driver=driver.user)

    services.set_truck_active(truck=truck, actor=actor, is_active=False)

    truck.refresh_from_db()
    assert (truck.is_active, truck.driver, truck.location.is_active) == (False, None, False)
    assert selectors.truck_of_driver(driver) is None
    with pytest.raises(ValidationError, match="archivé"):
        services.update_truck(truck=truck, actor=actor, driver=driver.user)
    # The driver can now be given another truck.
    assert new_truck(organization, actor, name="Camion 2", plate="102 TU 2002", driver=driver.user).pk

    services.set_truck_active(truck=truck, actor=actor, is_active=True)
    truck.refresh_from_db()
    assert (truck.is_active, truck.location.is_active) == (True, True)


# ---- own truck ----


def test_a_driver_may_use_only_the_location_of_their_own_active_truck(organization, actor):
    driver = driver_of(organization)
    other_driver = driver_of(organization)
    truck = new_truck(organization, actor, driver=driver.user)
    other = new_truck(organization, actor, name="Camion 2", plate="102 TU 2002", driver=other_driver.user)
    room = StockLocationFactory.create(organization=organization)
    owner = MembershipFactory.create(organization=organization, role=Role.OWNER)

    assert selectors.may_use_location(driver, truck.location_id)
    assert not selectors.may_use_location(driver, other.location_id)
    assert not selectors.may_use_location(driver, room.pk)
    assert selectors.may_use_location(owner, room.pk)
    assert selectors.may_use_truck(driver, truck)
    assert not selectors.may_use_truck(driver, other)


# ---- API ----


def client_for(membership):
    client = APIClient()
    client.force_authenticate(membership.user)
    return client


def test_the_owner_creates_a_truck_for_a_driver_and_the_driver_sees_it_in_the_session(organization):
    owner = MembershipFactory.create(organization=organization, role=Role.OWNER)
    driver = driver_of(organization)

    response = client_for(owner).post(
        reverse("truck-list"), {"name": "Camion 1", "plate": "101 TU 2001", "driver": driver.user.pk}, format="json"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["driver"]["id"] == driver.user.pk
    me = client_for(driver).get(reverse("me")).json()
    assert me["truck"] == {
        "id": body["id"],
        "name": "Camion 1",
        "plate": "101 TU 2001",
        "location_id": body["location_id"],
    }
    assert client_for(owner).get(reverse("me")).json()["truck"] is None


def test_a_driver_reads_only_their_own_truck_and_changes_nothing(organization, actor):
    driver = driver_of(organization)
    own = new_truck(organization, actor, driver=driver.user)
    other = new_truck(organization, actor, name="Camion 2", plate="102 TU 2002")
    client = client_for(driver)

    assert [row["id"] for row in client.get(reverse("truck-list")).json()] == [own.pk]
    assert client.get(reverse("truck-detail", args=[own.pk])).status_code == 200
    assert client.get(reverse("truck-detail", args=[other.pk])).status_code == 403
    assert client.patch(reverse("truck-detail", args=[own.pk]), {"name": "X"}, format="json").status_code == 403
    assert client.post(reverse("truck-archive", args=[own.pk])).status_code == 403


def test_a_driver_without_truck_sees_none(organization, actor):
    new_truck(organization, actor)

    assert client_for(driver_of(organization)).get(reverse("truck-list")).json() == []


def test_the_accountant_reads_every_truck_but_changes_none(organization, actor):
    truck = new_truck(organization, actor)
    client = client_for(MembershipFactory.create(organization=organization, role=Role.ACCOUNTANT))

    assert len(client.get(reverse("truck-list")).json()) == 1
    assert client.post(reverse("truck-archive", args=[truck.pk])).status_code == 403


def test_a_partial_update_keeps_the_driver_and_null_removes_it(organization, actor):
    driver = driver_of(organization)
    truck = new_truck(organization, actor, driver=driver.user)
    client = client_for(MembershipFactory.create(organization=organization, role=Role.MANAGER))
    url = reverse("truck-detail", args=[truck.pk])

    assert client.patch(url, {"plate": "999 tu 9999"}, format="json").json()["driver"]["id"] == driver.user.pk
    body = client.patch(url, {"driver": None}, format="json").json()
    assert (body["plate"], body["driver"]) == ("999 TU 9999", None)


def test_a_user_of_another_organization_is_an_unknown_driver(organization):
    owner = MembershipFactory.create(organization=organization, role=Role.OWNER)
    stranger = driver_of(OrganizationFactory.create())

    response = client_for(owner).post(
        reverse("truck-list"), {"name": "Camion 1", "plate": "101 TU 2001", "driver": stranger.user.pk}, format="json"
    )

    assert response.status_code == 400
    assert list(response.json()) == ["driver"]


def test_another_organization_trucks_are_invisible(organization, actor):
    truck = new_truck(OrganizationFactory.create(), actor)
    client = client_for(MembershipFactory.create(organization=organization, role=Role.OWNER))

    assert client.get(reverse("truck-list")).json() == []
    assert client.get(reverse("truck-detail", args=[truck.pk])).status_code == 404
