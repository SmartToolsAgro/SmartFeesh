"""The end of a driver's day (P3-T06, D-094): the summary, the counted cash and the office review."""

import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.tests.factories import ProductFactory, ProductPriceFactory
from apps.core.models import Role
from apps.core.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.fleet import services as fleet
from apps.inventory import services as inventory
from apps.inventory.models import MovementKind
from apps.inventory.tests.factories import BatchFactory, StockLocationFactory
from apps.partners import services as partners

pytestmark = pytest.mark.django_db


def client_for(membership):
    client = APIClient()
    client.force_authenticate(membership.user)
    return client


@pytest.fixture
def day():
    """A driver with a loaded truck: 12 kg of dorade at 28 DT, 50 DT in the till, day started."""
    organization = OrganizationFactory.create()
    actor = UserFactory.create()
    driver = MembershipFactory.create(organization=organization, role=Role.DRIVER)
    office = MembershipFactory.create(organization=organization, role=Role.MANAGER)
    room = StockLocationFactory.create(organization=organization, name="Chambre froide 1")
    truck = fleet.create_truck(
        organization=organization, actor=actor, name="Camion 1", plate="101 TU 2001", driver=driver.user
    )
    product = ProductFactory.create(organization=organization, name="Dorade royale", reference="DO-003")
    ProductPriceFactory.create(
        product=product, price=Decimal("28.000"), valid_from=timezone.now() - dt.timedelta(days=3)
    )
    batch = BatchFactory.create(organization=organization, product=product, received_on=timezone.localdate())
    inventory.post_movement(
        organization=organization,
        actor=None,
        kind=MovementKind.RECEIPT,
        batch=batch,
        quantity="20",
        to_location=room,
    )
    inventory.create_transfer(
        organization=organization,
        actor=actor,
        from_location=room,
        to_location=truck.location,
        transferred_on=timezone.localdate(),
        lines=[{"product": product, "quantity": Decimal("12")}],
        validate=True,
    )
    partners.ensure_walk_in_customer(organization=organization)
    api = client_for(driver)
    assert api.post(reverse("my-day"), {"opening_cash": "50"}, format="json").status_code == 201
    return {"api": api, "office": client_for(office), "product": product, "truck": truck}


def sell(day, kg, paid):
    return day["api"].post(
        reverse("sale-list"),
        {
            "location": day["truck"].location_id,
            "confirm_now": True,
            "amount_paid": paid,
            "payment_method": "cash",
            "lines": [{"product": day["product"].pk, "quantity": kg}],
        },
        format="json",
    )


def test_the_summary_adds_up_the_day(day):
    assert sell(day, "5", "100.000").status_code == 201  # 140 DT, 40 on credit

    summary = day["api"].get(reverse("my-day-summary")).json()["summary"]

    assert (summary["sales_count"], summary["sales_total"], summary["cash_received"], summary["on_credit"]) == (
        1,
        "140.000",
        "100.000",
        "40.000",
    )
    assert summary["expected_cash"] == "150.000"  # 50 at the start + 100 received
    assert summary["products"][0] | {"product_id": 0} == {
        "product_id": 0,
        "product_name": "Dorade royale",
        "loaded": "12.000",
        "sold": "5.000",
        "lost": "0.000",
        "returned": "0.000",
        "remaining": "7.000",
    }


def test_the_driver_sends_the_day_and_the_office_approves_it_after_a_justification(day):
    sell(day, "5", "100.000")

    sent = day["api"].post(
        reverse("my-day-closing"), {"counted_cash": "140.000", "note": "Un billet de 10 manque"}, format="json"
    )
    again = day["api"].post(reverse("my-day-closing"), {"counted_cash": "150.000"}, format="json")

    assert sent.status_code == 201
    assert sent.json()["closing"]["status"] == "submitted"
    assert again.status_code == 400  # already sent
    closing = day["office"].get(reverse("day-closing-list")).json()[0]
    assert (closing["expected_cash"], closing["counted_cash"], closing["difference"]) == (
        "150.000",
        "140.000",
        "-10.000",
    )
    detail = day["office"].get(reverse("day-closing-detail", args=[closing["id"]])).json()
    assert detail["driver_note"] == "Un billet de 10 manque"
    assert detail["summary"]["sales_total"] == "140.000"

    asked = day["office"].post(
        reverse("day-closing-justification", args=[closing["id"]]), {"reason": "Expliquez la différence"}, format="json"
    )
    assert asked.json()["status"] == "justification"
    resent = day["api"].post(
        reverse("my-day-closing"), {"counted_cash": "140.000", "note": "Dépense non saisie"}, format="json"
    )
    assert resent.status_code == 201
    approved = day["office"].post(reverse("day-closing-approve", args=[closing["id"]]))
    assert approved.json()["status"] == "approved"
    assert day["api"].post(reverse("my-day-closing"), {"counted_cash": "1"}, format="json").status_code == 400  # locked
    assert day["office"].post(reverse("day-closing-approve", args=[closing["id"]])).status_code == 400


def test_only_the_right_people_use_the_screens(day):
    assert day["office"].get(reverse("my-day-summary")).status_code == 403
    assert day["api"].get(reverse("day-closing-list")).status_code == 403
    assert client_for(MembershipFactory.create(role=Role.DRIVER)).get(reverse("my-day-summary")).status_code == 404
