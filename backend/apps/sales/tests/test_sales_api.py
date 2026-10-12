import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.tests.factories import ProductFactory, ProductPriceFactory
from apps.core.models import Role
from apps.core.tests.factories import MembershipFactory
from apps.fleet import services as fleet
from apps.inventory import services as stock
from apps.inventory.models import MovementKind
from apps.inventory.tests.factories import BatchFactory, StockLocationFactory
from apps.partners.tests.factories import CustomerFactory
from apps.sales import services
from apps.sales.models import Sale, SaleStatus

pytestmark = pytest.mark.django_db

FIRST_BL = f"BL-{timezone.localdate().year}-0001"


@pytest.fixture
def manager():
    return MembershipFactory.create(role=Role.MANAGER)


@pytest.fixture
def organization(manager):
    return manager.organization


def client_for(membership):
    client = APIClient()
    client.force_authenticate(membership.user)
    return client


@pytest.fixture
def api(manager):
    return client_for(manager)


@pytest.fixture
def customer(organization):
    return CustomerFactory.create(organization=organization, name="Restaurant Le Corail")


@pytest.fixture
def counter(organization):
    return StockLocationFactory.create(organization=organization, name="Chambre froide 1", counter_sales=True)


@pytest.fixture
def crevette(organization):
    product = ProductFactory.create(organization=organization, name="Crevette Royale", reference="CR-001")
    ProductPriceFactory.create(
        product=product, price=Decimal("42.000"), valid_from=timezone.now() - dt.timedelta(days=30)
    )
    return product


def receive(organization, product, location, kg, *, cost="20.000"):
    batch = BatchFactory.create(organization=organization, product=product, unit_cost=Decimal(cost))
    stock.post_movement(
        organization=organization, actor=None, kind=MovementKind.RECEIPT, batch=batch, quantity=kg, to_location=location
    )
    return batch


def create(api, location, lines, **fields):
    body = {"location": location.pk, "lines": lines}
    body.update(fields)
    return api.post(reverse("sale-list"), body, format="json")


@pytest.fixture
def driver_with_truck(organization, manager):
    """A driver whose usual truck is Camion 1: their truck of the day without an assignment (D-046)."""
    driver = MembershipFactory.create(role=Role.DRIVER, organization=organization)
    truck = fleet.create_truck(
        organization=organization, actor=manager.user, name="Camion 1", plate="101 TU 2001", driver=driver.user
    )
    return driver, truck.location


def test_the_office_sells_and_confirms_at_once_and_reads_the_lots_back(api, organization, customer, counter, crevette):
    batch = receive(organization, crevette, counter, "10")

    response = create(
        api,
        counter,
        [{"product": crevette.pk, "quantity": "5"}],
        customer=customer.pk,
        amount_paid="100.000",
        payment_method="cash",
        confirm_now=True,
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["number"], body["status"], body["total"], body["amount_due"]) == (
        FIRST_BL,
        "confirmed",
        "210.000",
        "110.000",
    )
    assert (body["cost_total"], body["margin"], body["tax_amount"]) == ("100.000", "110.000", None)
    assert body["location"] == {"id": counter.pk, "name": "Chambre froide 1", "kind": "cold_room"}
    (line,) = body["lines"]
    assert (line["unit_price"], line["price_source"], line["cost_amount"]) == ("42.000", "daily", "100.000")
    assert line["batches"] == [
        {
            "id": line["batches"][0]["id"],
            "batch": {"id": batch.pk, "number": batch.number},
            "quantity": "5.000",
            "unit_cost": "20.000",
            "cost_amount": "100.000",
            "revenue_amount": "210.000",
        }
    ]

    lot = api.get(reverse("batch-sales", args=[batch.pk])).json()
    assert (lot["quantity"], lot["revenue"], lot["cost"], lot["margin"]) == ("5.000", "210.000", "100.000", "110.000")
    assert [(row["sale"]["number"], row["customer"], row["quantity"]) for row in lot["rows"]] == [
        (FIRST_BL, "Restaurant Le Corail", "5.000")
    ]


def test_a_counter_sale_without_customer_goes_to_the_walk_in_customer(api, organization, counter, crevette):
    receive(organization, crevette, counter, "10")

    unpaid = create(api, counter, [{"product": crevette.pk, "quantity": "1"}], confirm_now=True)
    paid = create(
        api,
        counter,
        [{"product": crevette.pk, "quantity": "1"}],
        paid_in_full=True,
        payment_method="cash",
        confirm_now=True,
    )

    assert unpaid.status_code == 400
    assert "amount_paid" in unpaid.json()
    assert paid.status_code == 201
    assert paid.json()["customer"]["is_walk_in"] is True
    assert paid.json()["amount_paid"] == "42.000"


def test_line_errors_come_back_on_their_own_keys(api, organization, customer, counter, crevette):
    receive(organization, crevette, counter, "1")

    unknown = create(api, counter, [{"product": 999999, "quantity": "1"}], customer=customer.pk)
    short = create(api, counter, [{"product": crevette.pk, "quantity": "2"}], customer=customer.pk, confirm_now=True)

    assert unknown.status_code == 400
    assert unknown.json() == {"lines.0.product": ["Produit inconnu."]}
    assert short.status_code == 400
    assert "Stock insuffisant" in short.json()["lines.0.quantity"][0]
    assert not Sale.objects.exists()


def test_a_draft_is_changed_confirmed_then_cancelled_with_a_reason(api, organization, customer, counter, crevette):
    receive(organization, crevette, counter, "10")
    draft = create(api, counter, [{"product": crevette.pk, "quantity": "1"}], customer=customer.pk).json()

    changed = api.put(
        reverse("sale-detail", args=[draft["id"]]),
        {"location": counter.pk, "customer": customer.pk, "lines": [{"product": crevette.pk, "quantity": "3"}]},
        format="json",
    )
    confirmed = api.post(reverse("sale-confirm", args=[draft["id"]]))
    no_reason = api.post(reverse("sale-cancel", args=[draft["id"]]), {}, format="json")
    cancelled = api.post(reverse("sale-cancel", args=[draft["id"]]), {"reason": "Erreur"}, format="json")

    assert changed.json()["total"] == "126.000"
    assert confirmed.json()["status"] == "confirmed"
    assert no_reason.status_code == 400
    assert (cancelled.json()["status"], cancelled.json()["cancel_reason"]) == ("cancelled", "Erreur")
    listed = api.get(reverse("sale-list"), {"status": "cancelled"}).json()
    assert [row["number"] for row in listed["results"]] == [FIRST_BL]


def test_an_accepted_quote_is_converted_and_points_to_its_sale(api, manager, organization, customer, counter, crevette):
    receive(organization, crevette, counter, "10")
    quote = services.create_quote(
        organization=organization,
        actor=manager.user,
        customer=customer,
        quoted_on=timezone.localdate(),
        lines=[{"product": crevette, "quantity": "5"}],
        send=True,
    )
    services.accept_quote(quote=quote, actor=manager.user)

    response = api.post(
        reverse("quote-convert", args=[quote.pk]), {"location": counter.pk, "confirm_now": True}, format="json"
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["quote"], body["status"], body["total"]) == (
        {"id": quote.pk, "number": quote.number},
        "confirmed",
        "210.000",
    )
    shown = api.get(reverse("quote-detail", args=[quote.pk])).json()
    assert (shown["status"], shown["sale"]) == (
        "accepted",
        {"id": body["id"], "number": FIRST_BL, "status": "confirmed"},
    )
    assert api.get(reverse("quote-list")).json()["results"][0]["sale"]["number"] == FIRST_BL


# ---- permissions ----


def test_a_driver_sells_from_the_truck_of_the_day_only_and_never_sees_costs(
    organization, customer, counter, crevette, driver_with_truck
):
    driver, truck = driver_with_truck
    receive(organization, crevette, truck, "10")
    receive(organization, crevette, counter, "10")
    other_truck = StockLocationFactory.create(organization=organization, kind="truck", name="Camion 2")
    api = client_for(driver)
    yesterday = (timezone.now() - dt.timedelta(days=1)).isoformat()

    sold = create(
        api,
        truck,
        [{"product": crevette.pk, "quantity": "2"}],
        customer=customer.pk,
        sold_at=yesterday,
        confirm_now=True,
    )
    from_room = create(api, counter, [{"product": crevette.pk, "quantity": "1"}], customer=customer.pk)
    from_other = create(api, other_truck, [{"product": crevette.pk, "quantity": "1"}], customer=customer.pk)

    assert sold.status_code == 201
    body = sold.json()
    assert body["status"] == "confirmed"
    # A driver sells now, whatever the moment sent.
    assert dt.datetime.fromisoformat(body["sold_at"]).date() == timezone.localdate()
    assert (body["cost_total"], body["margin"]) == (None, None)
    assert (body["lines"][0]["cost_amount"], body["lines"][0]["batches"]) == (None, None)
    assert (from_room.status_code, from_other.status_code) == (403, 403)
    assert api.get(reverse("batch-sales", args=[1])).status_code == 403
    assert api.post(reverse("sale-cancel", args=[body["id"]]), {"reason": "x"}, format="json").status_code == 403


def test_a_driver_sees_only_their_own_sales(api, organization, customer, counter, crevette, driver_with_truck):
    driver, truck = driver_with_truck
    receive(organization, crevette, truck, "10")
    office_sale = create(api, counter, [{"product": crevette.pk, "quantity": "1"}], customer=customer.pk).json()
    driver_api = client_for(driver)
    own = create(driver_api, truck, [{"product": crevette.pk, "quantity": "1"}], customer=customer.pk).json()

    listed = driver_api.get(reverse("sale-list")).json()

    assert [row["number"] for row in listed["results"]] == [own["number"]]
    assert listed["results"][0]["cost_total"] is None
    assert driver_api.get(reverse("sale-detail", args=[office_sale["id"]])).status_code == 404
    # The office sees both.
    assert api.get(reverse("sale-list")).json()["count"] == 2


def test_the_accountant_reads_sales_but_never_sells(organization, customer, counter, crevette):
    accountant = client_for(MembershipFactory.create(role=Role.ACCOUNTANT, organization=organization))

    assert accountant.get(reverse("sale-list")).status_code == 200
    assert create(accountant, counter, [{"product": crevette.pk, "quantity": "1"}]).status_code == 403


def test_sales_of_another_organization_are_not_found(api, crevette):
    other = MembershipFactory.create(role=Role.OWNER)
    elsewhere = services.create_sale(
        organization=other.organization,
        actor=None,
        customer=CustomerFactory.create(organization=other.organization),
        location=StockLocationFactory.create(organization=other.organization, counter_sales=True),
        lines=[
            {
                "product": ProductPriceFactory.create(
                    product=ProductFactory.create(organization=other.organization)
                ).product,
                "quantity": "1",
            }
        ],
    )

    assert elsewhere.status == SaleStatus.DRAFT
    assert api.get(reverse("sale-detail", args=[elsewhere.pk])).status_code == 404
    assert api.post(reverse("sale-confirm", args=[elsewhere.pk])).status_code == 404


def test_logged_out_is_401():
    assert APIClient().get(reverse("sale-list")).status_code == 401
