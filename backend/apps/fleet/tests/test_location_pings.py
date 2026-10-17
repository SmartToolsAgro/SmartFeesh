"""The driver's phone sends its GPS points during a running day (D-164)."""

import datetime as dt
from decimal import Decimal
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import Role
from apps.core.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.fleet import selectors, services

pytestmark = pytest.mark.django_db


def point(minutes_ago=1, lat="34.740000", lng="10.760000", **extra):
    return {
        "client_uuid": str(uuid4()),
        "recorded_at": (timezone.now() - dt.timedelta(minutes=minutes_ago)).isoformat(),
        "latitude": lat,
        "longitude": lng,
        **extra,
    }


@pytest.fixture
def road():
    organization = OrganizationFactory.create()
    truck = services.create_truck(
        organization=organization, actor=UserFactory.create(), name="Camion 1", plate="101 TU 2001"
    )
    driver = MembershipFactory.create(organization=organization, role=Role.DRIVER)
    client = APIClient()
    client.force_authenticate(driver.user)
    return {"organization": organization, "truck": truck, "driver": driver, "client": client}


def open_day(road):
    return services.open_driver_day(
        organization=road["organization"],
        actor=road["driver"].user,
        truck=road["truck"],
        opening_cash=Decimal(0),
        date=timezone.localdate(),
    )


def test_points_wait_for_the_day_to_start(road):
    response = road["client"].post(reverse("my-locations"), {"points": [point()]}, format="json")

    assert response.status_code == 404


def test_points_are_stored_once_and_in_time_order(road):
    day = open_day(road)
    first, second = point(minutes_ago=5, accuracy="12.5"), point(minutes_ago=2, lat="34.741000")

    response = road["client"].post(reverse("my-locations"), {"points": [second, first]}, format="json")
    again = road["client"].post(reverse("my-locations"), {"points": [first]}, format="json")

    assert (response.status_code, response.json()) == (200, {"saved": 2})
    assert again.json() == {"saved": 1}
    pings = list(selectors.pings_of_day(day))
    assert [str(p.client_uuid) for p in pings] == [first["client_uuid"], second["client_uuid"]]
    assert str(pings[0].accuracy) == "12.5"


def test_future_points_and_points_after_the_closing_are_dropped(road):
    day = open_day(road)
    services.end_driver_day(driver_day=day, ended_at=timezone.now() - dt.timedelta(minutes=10))

    response = road["client"].post(
        reverse("my-locations"),
        {"points": [point(minutes_ago=30), point(minutes_ago=3), point(minutes_ago=-60)]},
        format="json",
    )

    assert response.json() == {"saved": 1}
    assert selectors.pings_of_day(day).count() == 1


def test_a_point_off_the_earth_or_a_big_batch_is_refused(road):
    open_day(road)
    url = reverse("my-locations")

    assert road["client"].post(url, {"points": [point(lat="91")]}, format="json").status_code == 400
    assert road["client"].post(url, {"points": []}, format="json").status_code == 400
    assert road["client"].post(url, {"points": [point() for _ in range(201)]}, format="json").status_code == 400


def test_only_a_driver_sends_points(road):
    manager = MembershipFactory.create(organization=road["organization"], role=Role.MANAGER)
    client = APIClient()
    client.force_authenticate(manager.user)

    assert client.post(reverse("my-locations"), {"points": [point()]}, format="json").status_code == 403
