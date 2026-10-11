import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.models import Role
from apps.core.tests.factories import MembershipFactory
from apps.partners import services

pytestmark = pytest.mark.django_db


def test_a_driver_finds_customers_by_name_and_only_a_driver_does():
    driver = MembershipFactory.create(role=Role.DRIVER)
    services.ensure_walk_in_customer(organization=driver.organization)
    services.create_customer(organization=driver.organization, actor=driver.user, name="Restaurant Le Port")
    services.create_customer(organization=driver.organization, actor=driver.user, name="Hôtel Marina")
    client = APIClient()
    client.force_authenticate(driver.user)

    found = client.get(reverse("my-customers"), {"search": "port"}).json()
    everyone = client.get(reverse("my-customers")).json()

    assert [c["name"] for c in found] == ["Restaurant Le Port"]
    assert [c["is_walk_in"] for c in everyone] == [False, False, True]  # the walk-in customer is last
    manager = APIClient()
    manager.force_authenticate(MembershipFactory.create(role=Role.MANAGER).user)
    assert manager.get(reverse("my-customers")).status_code == 403
