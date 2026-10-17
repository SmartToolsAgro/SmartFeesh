"""Truck of the day (P1-T12, D-046): one driver per truck and one truck per driver each day."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import AuditLog, Role
from apps.core.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.fleet import selectors, services
from apps.fleet.models import TruckAssignment

pytestmark = pytest.mark.django_db


@pytest.fixture
def organization():
    return OrganizationFactory.create()


@pytest.fixture
def actor():
    return UserFactory.create()


@pytest.fixture
def today():
    return timezone.localdate()


def driver_of(organization):
    return MembershipFactory.create(organization=organization, role=Role.DRIVER)


def member(organization, role):
    return MembershipFactory.create(organization=organization, role=role)


def new_truck(organization, actor, number=1, **fields):
    return services.create_truck(
        organization=organization, actor=actor, name=f"Camion {number}", plate=f"10{number} TU 200{number}", **fields
    )


def assign(organization, actor, truck, driver, day, **fields):
    return services.assign_truck(
        organization=organization, actor=actor, truck=truck, driver=driver.user, date=day, **fields
    )


def client_for(membership):
    client = APIClient()
    client.force_authenticate(membership.user)
    return client


# ---- services ----


def test_a_truck_is_given_to_a_driver_for_a_day_with_an_audit_entry(organization, actor, today):
    truck, driver = new_truck(organization, actor), driver_of(organization)

    assignment = assign(organization, actor, truck, driver, today)

    assert (assignment.truck, assignment.driver, assignment.date) == (truck, driver.user, today)
    entry = AuditLog.objects.get(action="truck_assignment.created")
    assert entry.after == {"truck": "Camion 1", "driver": driver.user.username, "date": today.isoformat()}
    # Asking again for the same pair changes nothing.
    assert assign(organization, actor, truck, driver, today).pk == assignment.pk
    assert TruckAssignment.objects.count() == 1


def test_one_driver_per_truck_per_day_with_a_clear_message(organization, actor, today):
    truck, first, second = new_truck(organization, actor), driver_of(organization), driver_of(organization)
    assign(organization, actor, truck, first, today)

    with pytest.raises(ValidationError, match="est déjà attribué à") as caught:
        assign(organization, actor, truck, second, today)
    assert list(caught.value.message_dict) == ["truck"]
    # Another day is free.
    assert assign(organization, actor, truck, second, today + timedelta(days=1)).pk


def test_one_truck_per_driver_per_day_with_a_clear_message(organization, actor, today):
    one, two, driver = new_truck(organization, actor), new_truck(organization, actor, 2), driver_of(organization)
    assign(organization, actor, one, driver, today)

    with pytest.raises(ValidationError, match="conduit déjà Camion 1") as caught:
        assign(organization, actor, two, driver, today)
    assert list(caught.value.message_dict) == ["driver"]
    assert assign(organization, actor, two, driver, today + timedelta(days=1)).pk


def test_a_driver_may_swap_their_own_truck_when_replacing(organization, actor, today):
    one, two, driver = new_truck(organization, actor), new_truck(organization, actor, 2), driver_of(organization)
    assignment = assign(organization, actor, one, driver, today)

    swapped = assign(organization, actor, two, driver, today, replace=True)

    assert swapped.pk == assignment.pk
    assert TruckAssignment.objects.get().truck == two
    entry = AuditLog.objects.get(action="truck_assignment.changed")
    assert (entry.before, entry.after) == ({"truck": "Camion 1"}, {"truck": "Camion 2"})


def test_replacing_never_takes_a_truck_from_another_driver(organization, actor, today):
    one, two = new_truck(organization, actor), new_truck(organization, actor, 2)
    first, second = driver_of(organization), driver_of(organization)
    assign(organization, actor, one, first, today)
    assign(organization, actor, two, second, today)

    with pytest.raises(ValidationError, match="est déjà attribué"):
        assign(organization, actor, two, first, today, replace=True)


def test_only_a_driver_of_the_company_and_an_active_truck(organization, actor, today):
    truck = new_truck(organization, actor)
    manager = member(organization, Role.MANAGER)
    stranger = driver_of(OrganizationFactory.create())

    for user in (manager, stranger):
        with pytest.raises(ValidationError, match="pas un chauffeur"):
            assign(organization, actor, truck, user, today)

    services.set_truck_active(truck=truck, actor=actor, is_active=False)
    with pytest.raises(ValidationError, match="archivé"):
        assign(organization, actor, truck, driver_of(organization), today)


def test_the_database_refuses_a_second_driver_or_truck_for_the_day(organization, actor, today):
    one, two = new_truck(organization, actor), new_truck(organization, actor, 2)
    first, second = driver_of(organization), driver_of(organization)
    assign(organization, actor, one, first, today)

    for truck, driver in [(one, second), (two, first)]:
        with pytest.raises(IntegrityError), transaction.atomic():
            TruckAssignment.objects.create(organization=organization, truck=truck, driver=driver.user, date=today)


def test_removing_an_assignment_keeps_it_in_the_audit_trail(organization, actor, today):
    truck, driver = new_truck(organization, actor), driver_of(organization)
    assignment = assign(organization, actor, truck, driver, today)

    services.unassign_truck(assignment=assignment, actor=actor)

    assert not TruckAssignment.objects.exists()
    entry = AuditLog.objects.get(action="truck_assignment.removed")
    assert entry.before == {"truck": "Camion 1", "driver": driver.user.username, "date": today.isoformat()}


def test_archiving_a_truck_drops_its_days_to_come_and_keeps_the_past(organization, actor, today):
    truck, driver = new_truck(organization, actor), driver_of(organization)
    yesterday = assign(organization, actor, truck, driver, today - timedelta(days=1))
    assign(organization, actor, truck, driver, today)
    assign(organization, actor, truck, driver, today + timedelta(days=1))

    services.set_truck_active(truck=truck, actor=actor, is_active=False)

    assert list(TruckAssignment.objects.all()) == [yesterday]


# ---- the driver's truck of the day ----


def test_the_assignment_of_the_day_wins_over_the_usual_truck(organization, actor, today):
    driver = driver_of(organization)
    usual = new_truck(organization, actor, driver=driver.user)
    other = new_truck(organization, actor, 2)
    room_owner = member(organization, Role.OWNER)

    assert selectors.truck_of_driver(driver) == usual  # fallback: nothing assigned
    assign(organization, actor, other, driver, today)

    assert selectors.truck_of_driver(driver) == other
    assert selectors.may_use_truck(driver, other)
    assert not selectors.may_use_truck(driver, usual)
    assert selectors.may_use_location(driver, other.location_id)
    assert not selectors.may_use_location(driver, usual.location_id)
    assert selectors.may_use_location(room_owner, usual.location_id)
    # Tomorrow nothing is assigned: the usual truck again.
    assert selectors.truck_of_driver(driver, today + timedelta(days=1)) == usual


def test_the_usual_truck_goes_to_the_driver_assigned_to_it_that_day(organization, actor, today):
    usual_driver, substitute = driver_of(organization), driver_of(organization)
    truck = new_truck(organization, actor, driver=usual_driver.user)
    assign(organization, actor, truck, substitute, today)

    assert selectors.truck_of_driver(substitute) == truck
    assert selectors.truck_of_driver(usual_driver) is None
    assert not selectors.may_use_truck(usual_driver, truck)
    assert not selectors.may_use_location(usual_driver, truck.location_id)


def test_a_driver_without_usual_truck_or_assignment_has_none(organization, actor):
    new_truck(organization, actor)

    assert selectors.truck_of_driver(driver_of(organization)) is None
    assert selectors.truck_of_driver(member(organization, Role.OWNER)) is None


# ---- API ----


def test_the_session_shows_the_truck_of_the_day(organization, actor, today):
    driver = driver_of(organization)
    usual = new_truck(organization, actor, driver=driver.user)
    other = new_truck(organization, actor, 2)
    client = client_for(driver)
    assert client.get(reverse("me")).json()["truck"]["id"] == usual.pk

    assign(organization, actor, other, driver, today)

    assert client.get(reverse("me")).json()["truck"]["id"] == other.pk
    assert [row["id"] for row in client.get(reverse("truck-list")).json()] == [other.pk]


def test_the_owner_assigns_lists_and_removes_a_day(organization, actor, today):
    owner, driver = member(organization, Role.OWNER), driver_of(organization)
    truck = new_truck(organization, actor)
    client = client_for(owner)

    created = client.post(
        reverse("truck-assignment-list"),
        {"truck": truck.pk, "driver": driver.user.pk, "date": today.isoformat()},
        format="json",
    )
    assert created.status_code == 201
    body = created.json()
    assert (body["truck_id"], body["truck_name"], body["driver"]["id"]) == (truck.pk, "Camion 1", driver.user.pk)

    listed = client.get(reverse("truck-assignment-list"), {"date": today.isoformat()}).json()
    assert [row["id"] for row in listed] == [body["id"]]
    assert client.get(reverse("truck-assignment-list"), {"date": "2020-01-01"}).json() == []

    assert client.delete(reverse("truck-assignment-detail", args=[body["id"]])).status_code == 204
    assert client.get(reverse("truck-assignment-list")).json() == []


def test_the_api_reports_a_second_claim_on_the_truck_field(organization, actor, today):
    owner = member(organization, Role.OWNER)
    truck, first, second = new_truck(organization, actor), driver_of(organization), driver_of(organization)
    assign(organization, actor, truck, first, today)

    response = client_for(owner).post(
        reverse("truck-assignment-list"), {"truck": truck.pk, "driver": second.user.pk}, format="json"
    )

    assert response.status_code == 400
    assert list(response.json()) == ["truck"]


def test_a_driver_takes_a_truck_for_themselves_and_may_change_it(organization, actor, today):
    driver = driver_of(organization)
    one, two = new_truck(organization, actor), new_truck(organization, actor, 2)
    client = client_for(driver)
    url = reverse("truck-assignment-list")

    first = client.post(url, {"truck": one.pk}, format="json")
    assert first.status_code == 201
    assert first.json()["driver"]["id"] == driver.user.pk
    assert client.get(reverse("me")).json()["truck"]["id"] == one.pk

    second = client.post(url, {"truck": two.pk}, format="json")
    assert second.status_code == 201
    assert client.get(reverse("me")).json()["truck"]["id"] == two.pk
    assert TruckAssignment.objects.count() == 1


def test_a_driver_cannot_assign_someone_else_or_a_past_day_or_remove_another_day(organization, actor, today):
    driver, colleague = driver_of(organization), driver_of(organization)
    truck = new_truck(organization, actor)
    mine = assign(organization, actor, truck, colleague, today)
    other = new_truck(organization, actor, 2)
    client = client_for(driver)
    url = reverse("truck-assignment-list")

    assert client.post(url, {"truck": other.pk, "driver": colleague.user.pk}, format="json").status_code == 403
    past = client.post(url, {"truck": other.pk, "date": (today - timedelta(days=1)).isoformat()}, format="json")
    assert past.status_code == 400
    assert list(past.json()) == ["date"]
    assert client.delete(reverse("truck-assignment-detail", args=[mine.pk])).status_code == 404
    # A driver sees only their own rows.
    assert client.get(url).json() == []
    assert TruckAssignment.objects.count() == 1


def test_the_accountant_reads_the_day_but_changes_nothing(organization, actor, today):
    accountant = member(organization, Role.ACCOUNTANT)
    truck, driver = new_truck(organization, actor), driver_of(organization)
    assignment = assign(organization, actor, truck, driver, today)
    client = client_for(accountant)

    assert len(client.get(reverse("truck-assignment-list")).json()) == 1
    assert client.post(reverse("truck-assignment-list"), {"truck": truck.pk}, format="json").status_code == 403
    assert client.delete(reverse("truck-assignment-detail", args=[assignment.pk])).status_code == 403


def test_assignments_of_another_organization_are_invisible(organization, actor, today):
    other = OrganizationFactory.create()
    truck, driver = new_truck(other, actor), driver_of(other)
    assignment = assign(other, actor, truck, driver, today)
    client = client_for(member(organization, Role.OWNER))

    assert client.get(reverse("truck-assignment-list")).json() == []
    assert client.delete(reverse("truck-assignment-detail", args=[assignment.pk])).status_code == 404
    posted = client.post(reverse("truck-assignment-list"), {"truck": truck.pk, "driver": driver.user.pk}, format="json")
    assert posted.status_code == 400


# ---- maintenance, breakdown and a truck left free (D-163) ----


def test_a_truck_in_maintenance_is_not_taken_and_loses_its_coming_days(organization, actor, today):
    truck, driver = new_truck(organization, actor, driver=None), driver_of(organization)
    assign(organization, actor, truck, driver, today)

    services.update_truck(truck=truck, actor=actor, condition="maintenance")

    assert not TruckAssignment.objects.filter(truck=truck).exists()
    with pytest.raises(ValidationError):
        assign(organization, actor, truck, driver, today)
    services.update_truck(truck=truck, actor=actor, condition="ok")
    assert assign(organization, actor, truck, driver, today).truck == truck


def test_a_truck_in_breakdown_is_not_the_usual_trucks_of_its_driver(organization, actor):
    driver = driver_of(organization)
    truck = new_truck(organization, actor, driver=driver.user)
    assert selectors.truck_of_driver(driver) == truck

    services.update_truck(truck=truck, actor=actor, condition="breakdown")

    assert selectors.truck_of_driver(driver) is None


def test_a_truck_left_free_has_no_driver_that_day_and_a_driver_can_take_it(organization, actor, today):
    usual = driver_of(organization)
    other = driver_of(organization)
    truck = new_truck(organization, actor, driver=usual.user)

    freed = services.assign_truck(organization=organization, actor=actor, truck=truck, driver=None, date=today)

    assert freed.driver is None
    assert selectors.truck_of_driver(usual) is None
    taken = assign(organization, actor, truck, other, today)
    assert (taken.pk, taken.driver) == (freed.pk, other.user)
