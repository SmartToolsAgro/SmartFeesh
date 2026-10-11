import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.tests.factories import ProductFactory
from apps.core.models import Role
from apps.core.tests.factories import MembershipFactory, OrganizationFactory
from apps.inventory import selectors, services
from apps.inventory.models import LocationKind, MovementKind

from .factories import BatchFactory, StockLocationFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def organization():
    return OrganizationFactory.create()


@pytest.fixture
def cold_room(organization):
    return StockLocationFactory.create(organization=organization, name="Chambre froide 1")


@pytest.fixture
def truck(organization):
    return StockLocationFactory.create(organization=organization, kind=LocationKind.TRUCK, name="Camion 1")


@pytest.fixture
def dorade(organization):
    return ProductFactory.create(organization=organization, name="Dorade royale", min_stock="50")


def receive(organization, product, location, kg, cost, *, days_ago=0):
    batch = BatchFactory.create(
        organization=organization,
        product=product,
        unit_cost=cost,
        received_on=timezone.localdate() - dt.timedelta(days=days_ago),
    )
    services.post_movement(
        organization=organization, actor=None, kind=MovementKind.RECEIPT, batch=batch, quantity=kg, to_location=location
    )
    return batch


def client_for(role, organization=None):
    membership = MembershipFactory.create(role=role, organization=organization or OrganizationFactory.create())
    client = APIClient()
    client.force_authenticate(membership.user)
    return client, membership


# ---- selectors ----


def test_the_average_cost_is_weighted_by_the_kg_still_on_hand(organization, cold_room, dorade):
    old = receive(organization, dorade, cold_room, "10", "20.000", days_ago=3)
    receive(organization, dorade, cold_room, "30", "28.000", days_ago=1)

    # (10 x 20 + 30 x 28) / 40
    assert selectors.average_purchase_cost(organization, product_id=dorade.pk) == Decimal("26.000")
    stock = selectors.product_stock(organization, dorade.pk)
    assert (stock.quantity, stock.average_cost, stock.last_cost) == (
        Decimal("40.000"),
        Decimal("26.000"),
        Decimal("28.000"),
    )

    # Once the oldest batch is sold, only what is left counts.
    services.post_movement(
        organization=organization, actor=None, kind=MovementKind.SALE, batch=old, quantity="10", from_location=cold_room
    )
    assert selectors.average_purchase_cost(organization, product_id=dorade.pk) == Decimal("28.000")


def test_a_product_without_stock_has_no_average_but_keeps_its_last_cost(organization, cold_room, dorade):
    batch = receive(organization, dorade, cold_room, "5", "21.500")
    services.post_movement(
        organization=organization,
        actor=None,
        kind=MovementKind.LOSS,
        batch=batch,
        quantity="5",
        from_location=cold_room,
        reason="Abîmé",
    )

    stock = selectors.product_stock(organization, dorade.pk)
    assert (stock.quantity, stock.average_cost, stock.last_cost) == (Decimal("0.000"), None, Decimal("21.500"))
    assert stock.is_low


def test_location_totals_give_kg_and_value_per_location(organization, cold_room, truck, dorade):
    batch = receive(organization, dorade, cold_room, "30", "20.000")
    services.post_movement(
        organization=organization,
        actor=None,
        kind=MovementKind.TRANSFER,
        batch=batch,
        quantity="12.500",
        from_location=cold_room,
        to_location=truck,
    )

    totals = {total.location.name: (total.quantity, total.value) for total in selectors.location_totals(organization)}
    assert totals == {
        "Chambre froide 1": (Decimal("17.500"), Decimal("350.000")),
        "Camion 1": (Decimal("12.500"), Decimal("250.000")),
    }


def test_the_low_stock_warning_compares_the_total_with_the_minimum(organization, cold_room, truck, dorade):
    batch = receive(organization, dorade, cold_room, "30", "20.000")
    receive(organization, dorade, truck, "20", "20.000")
    ProductFactory.create(organization=organization, name="Moules", min_stock="0")

    by_name = {stock.product.name: stock for stock in selectors.product_stocks(organization)}
    assert not by_name["Dorade royale"].is_low  # 50 kg in total, 50 required
    assert "Moules" not in by_name  # no stock and no minimum: not shown

    services.post_movement(
        organization=organization,
        actor=None,
        kind=MovementKind.LOSS,
        batch=batch,
        quantity="1",
        from_location=cold_room,
        reason="Abîmé",
    )
    assert {s.product.name: s for s in selectors.product_stocks(organization)}["Dorade royale"].is_low


def test_an_empty_product_with_a_minimum_shows_as_low(organization, dorade):
    stocks = selectors.product_stocks(organization)
    assert [(stock.product.pk, stock.quantity, stock.is_low) for stock in stocks] == [
        (dorade.pk, Decimal("0.000"), True)
    ]


def test_movements_filter_by_kind_and_dates(organization, cold_room, truck, dorade):
    batch = receive(organization, dorade, cold_room, "30", "20.000")
    old = services.post_movement(
        organization=organization,
        actor=None,
        kind=MovementKind.TRANSFER,
        batch=batch,
        quantity="5",
        from_location=cold_room,
        to_location=truck,
        occurred_at=timezone.now() - dt.timedelta(days=10),
    )
    today = timezone.localdate()

    assert list(selectors.movements_of(organization, kind=MovementKind.TRANSFER)) == [old]
    assert list(selectors.movements_of(organization, date_to=today - dt.timedelta(days=5))) == [old]
    assert [m.kind for m in selectors.movements_of(organization, date_from=today - dt.timedelta(days=5))] == [
        MovementKind.RECEIPT
    ]
    assert len(selectors.movements_of(organization, location_id=truck.pk)) == 1


# ---- API ----


def test_the_overview_lists_locations_and_products(organization, cold_room, truck, dorade):
    client, _ = client_for(Role.MANAGER, organization)
    receive(organization, dorade, cold_room, "30", "20.000", days_ago=2)
    receive(organization, dorade, truck, "10", "30.000", days_ago=1)

    body = client.get(reverse("stock-overview")).json()

    rooms = {row["name"]: row for row in body["locations"]}
    assert (rooms["Chambre froide 1"]["quantity"], rooms["Chambre froide 1"]["value"]) == ("30.000", "600.000")
    (product,) = body["products"]
    assert product["name"] == "Dorade royale"
    assert (product["quantity"], product["is_low"], product["min_stock"]) == ("40.000", True, "50.000")
    assert (product["average_cost"], product["last_cost"]) == ("22.500", "30.000")
    assert {row["location_id"]: row["quantity"] for row in product["locations"]} == {
        cold_room.pk: "30.000",
        truck.pk: "10.000",
    }


def test_the_product_page_lists_the_batches_on_hand(organization, cold_room, truck, dorade):
    client, _ = client_for(Role.OWNER, organization)
    first = receive(organization, dorade, cold_room, "30", "20.000", days_ago=2)
    receive(organization, dorade, truck, "10", "30.000", days_ago=1)
    services.post_movement(
        organization=organization,
        actor=None,
        kind=MovementKind.TRANSFER,
        batch=first,
        quantity="5",
        from_location=cold_room,
        to_location=truck,
    )

    body = client.get(reverse("stock-product", args=[dorade.pk])).json()

    assert len(body["batches"]) == 2
    oldest = body["batches"][0]
    assert (oldest["quantity"], oldest["value"], oldest["unit_cost"]) == ("30.000", "600.000", "20.000")
    assert {row["location"]["name"]: row["quantity"] for row in oldest["locations"]} == {
        "Chambre froide 1": "25.000",
        "Camion 1": "5.000",
    }


def test_the_movement_list_is_paginated_and_filtered(organization, cold_room, truck, dorade):
    client, _ = client_for(Role.OWNER, organization)
    batch = receive(organization, dorade, cold_room, "30", "20.000")
    services.post_movement(
        organization=organization,
        actor=None,
        kind=MovementKind.TRANSFER,
        batch=batch,
        quantity="5",
        from_location=cold_room,
        to_location=truck,
    )

    everything = client.get(reverse("movement-list"), {"limit": 1}).json()
    assert everything["count"] == 2
    assert everything["results"][0]["kind"] == "transfer"
    assert everything["results"][0]["from_location"]["name"] == "Chambre froide 1"

    receipts = client.get(reverse("movement-list"), {"kind": "receipt", "product": dorade.pk}).json()
    assert [row["kind"] for row in receipts["results"]] == ["receipt"]
    assert receipts["results"][0]["from_location"] is None
    assert client.get(reverse("movement-list"), {"kind": "nonsense"}).status_code == 400


def test_other_organizations_and_drivers_see_nothing(organization, cold_room, dorade):
    receive(organization, dorade, cold_room, "30", "20.000")
    stranger, _ = client_for(Role.OWNER)

    assert stranger.get(reverse("stock-overview")).json() == {"locations": [], "products": []}
    assert stranger.get(reverse("stock-product", args=[dorade.pk])).status_code == 404
    assert stranger.get(reverse("movement-list")).json()["count"] == 0

    driver, _ = client_for(Role.DRIVER, organization)
    for name, args in (("stock-overview", []), ("stock-product", [dorade.pk]), ("movement-list", [])):
        assert driver.get(reverse(name, args=args)).status_code == 403
    assert APIClient().get(reverse("stock-overview")).status_code == 401
