import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.tests.factories import ProductFactory
from apps.core.models import Role
from apps.core.tests.factories import MembershipFactory
from apps.expenses import selectors
from apps.fleet import services as fleet
from apps.inventory import services as inventory
from apps.inventory.models import MovementKind
from apps.inventory.tests.factories import BatchFactory, StockLocationFactory


@pytest.fixture
def manager(db):
    return MembershipFactory.create(role=Role.MANAGER)


@pytest.fixture
def organization(manager):
    return manager.organization


@pytest.fixture
def actor(manager):
    return manager.user


def member(organization, role):
    return MembershipFactory.create(organization=organization, role=role)


def client_for(membership):
    client = APIClient()
    client.force_authenticate(membership.user)
    return client


@pytest.fixture
def api(manager):
    return client_for(manager)


def category(organization, code):
    return selectors.category_by_code(organization, code)


@pytest.fixture
def fuel(organization):
    return category(organization, "fuel")


@pytest.fixture
def cold_room(organization):
    return StockLocationFactory.create(organization=organization, name="Chambre froide 1")


@pytest.fixture
def truck(organization, actor):
    return fleet.create_truck(organization=organization, actor=actor, name="Camion 2", plate="102 TU 2002")


def days_ago(days: int) -> dt.date:
    return timezone.localdate() - dt.timedelta(days=days)


def receive(organization, name, kg, location, *, received_on=None, number=None):
    """A lot of `kg` of a new product, put in `location`."""
    product = ProductFactory.create(organization=organization, name=name)
    fields: dict[str, Any] = {"received_on": received_on or days_ago(5)}
    if number is not None:
        fields["number"] = number
    batch = BatchFactory.create(organization=organization, product=product, **fields)
    inventory.post_movement(
        organization=organization, actor=None, kind=MovementKind.RECEIPT, batch=batch, quantity=kg, to_location=location
    )
    return batch


def load(organization, actor, source, truck, lines, *, day=None):
    """A validated load of (batch's product, kg) lines into the truck on `day`."""
    return inventory.create_transfer(
        organization=organization,
        actor=actor,
        from_location=source,
        to_location=truck.location,
        transferred_on=day or timezone.localdate(),
        lines=[{"product": batch.product, "quantity": kg, "unit_price": Decimal("30.000")} for batch, kg in lines],
        validate=True,
    )
