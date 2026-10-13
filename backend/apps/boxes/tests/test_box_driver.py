"""Returnable boxes on the road (P1-T14d, D-122): boxes left with a client by a sale, boxes collected back on a
pickup visit, and the driver's day view. Boxes move through the ledger; kilos through the stock, in one transaction."""

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.boxes import selectors
from apps.boxes import services as box_services
from apps.boxes.models import BoxMovement, BoxMovementKind, BoxPickup
from apps.catalog.tests.factories import ProductFactory, ProductPriceFactory
from apps.core.models import Role
from apps.core.tests.factories import MembershipFactory, OrganizationFactory
from apps.fleet import services as fleet
from apps.inventory import services as stock
from apps.inventory.models import MovementKind, StockMovement
from apps.inventory.tests.factories import BatchFactory, StockLocationFactory
from apps.partners.tests.factories import CustomerFactory, SupplierFactory
from apps.sales.models import Sale

pytestmark = pytest.mark.django_db


@pytest.fixture
def manager():
    return MembershipFactory.create(role=Role.MANAGER)


@pytest.fixture
def organization(manager):
    return manager.organization


@pytest.fixture
def driver(organization):
    return MembershipFactory.create(role=Role.DRIVER, organization=organization)


@pytest.fixture
def truck(organization, manager, driver):
    """Camion 1, the usual truck of the driver: their truck of the day (D-046)."""
    return fleet.create_truck(
        organization=organization, actor=manager.user, name="Camion 1", plate="101 TU 2001", driver=driver.user
    )


@pytest.fixture
def cold_room(organization):
    return StockLocationFactory.create(organization=organization, name="Chambre froide 1", counter_sales=True)


@pytest.fixture
def supplier(organization):
    return SupplierFactory.create(organization=organization, name="Mareyeur Port de Sfax")


@pytest.fixture
def customer(organization):
    return CustomerFactory.create(organization=organization, name="Restaurant Le Corail")


@pytest.fixture
def dorade(organization):
    product = ProductFactory.create(organization=organization, name="Dorade royale", reference="DO-003")
    ProductPriceFactory.create(
        product=product, price=Decimal("42.000"), valid_from=timezone.now() - dt.timedelta(days=30)
    )
    return product


def client_for(membership):
    client = APIClient()
    client.force_authenticate(membership.user)
    return client


def receive_kg(organization, product, location, kg):
    batch = BatchFactory.create(organization=organization, product=product, unit_cost=Decimal("20.000"))
    stock.post_movement(
        organization=organization, actor=None, kind=MovementKind.RECEIPT, batch=batch, quantity=kg, to_location=location
    )


def load_boxes(organization, actor, supplier, cold_room, truck_location, *, small=0, big=0):
    """Boxes received from the supplier, then loaded on the truck (both ledger movements, D-122)."""
    counts = {"small": small, "big": big}
    room = box_services.holder_for(organization=organization, location=cold_room)
    box_services.post_box_counts(
        organization=organization,
        actor=actor,
        kind=BoxMovementKind.RECEIVE,
        counts=counts,
        from_holder=box_services.holder_for(organization=organization, supplier=supplier),
        to_holder=room,
    )
    box_services.post_box_counts(
        organization=organization,
        actor=actor,
        kind=BoxMovementKind.LOAD,
        counts=counts,
        from_holder=room,
        to_holder=box_services.holder_for(organization=organization, location=truck_location),
    )


def boxes_held(organization, *, location=None, customer=None, box_type="small") -> int:
    if location is not None:
        holder = box_services.holder_for(organization=organization, location=location)
    else:
        holder = box_services.holder_for(organization=organization, customer=customer)
    return selectors.signed_balance(holder, box_type)


def backdate(movement: BoxMovement, days: int) -> None:
    """Move a posted movement into the past: the ledger is append-only, so a test writes the column itself."""
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE boxes_boxmovement SET created_at = %s WHERE id = %s",
            [timezone.now() - dt.timedelta(days=days), movement.pk],
        )


def sell(api, truck_location, customer, product, *, kg="2", paid="84.000", boxes=None, confirm=True):
    body = {
        "location": truck_location.pk,
        "customer": customer.pk,
        "lines": [{"product": product.pk, "quantity": kg}],
        "amount_paid": paid,
        "payment_method": "cash",
        "confirm_now": confirm,
    }
    if boxes is not None:
        body["boxes"] = boxes
    return api.post(reverse("sale-list"), body, format="json")


@pytest.fixture
def stocked_truck(organization, manager, supplier, cold_room, truck, dorade):
    """The truck holds 10 kg of dorade, 5 small boxes and 2 big boxes."""
    receive_kg(organization, dorade, truck.location, "10")
    load_boxes(organization, manager.user, supplier, cold_room, truck.location, small=5, big=2)
    return truck


# ---- Sale on the road ----


def test_a_driver_sale_leaves_boxes_with_the_client(organization, stocked_truck, customer, dorade, driver):
    response = sell(client_for(driver), stocked_truck.location, customer, dorade, boxes={"small": 3, "big": 0})

    assert response.status_code == 201
    assert (boxes_held(organization, customer=customer), boxes_held(organization, location=stocked_truck.location)) == (
        3,
        2,
    )
    (leave,) = BoxMovement.objects.filter(kind=BoxMovementKind.LEAVE)
    assert (leave.box_type, leave.count, leave.source_id) == ("small", 3, Sale.objects.get().pk)


def test_a_sale_without_boxes_or_with_zero_posts_no_box_movement(organization, stocked_truck, customer, dorade, driver):
    api = client_for(driver)
    omitted = sell(api, stocked_truck.location, customer, dorade, kg="1", paid="42.000")
    zero = sell(api, stocked_truck.location, customer, dorade, kg="1", paid="42.000", boxes={"small": 0, "big": 0})

    assert (omitted.status_code, zero.status_code) == (201, 201)
    assert not BoxMovement.objects.filter(kind=BoxMovementKind.LEAVE).exists()
    assert boxes_held(organization, location=stocked_truck.location) == 5


def test_a_sale_the_truck_cannot_box_is_refused_and_leaves_no_trace(
    organization, stocked_truck, customer, dorade, driver
):
    response = sell(client_for(driver), stocked_truck.location, customer, dorade, boxes={"small": 6})

    assert response.status_code == 400
    assert "boxes" in response.json()
    assert "Pas assez de petite caisse" in str(response.json())
    # Nothing of the sale survives: no sale, no kilos taken, no box left the truck.
    assert not Sale.objects.exists()
    assert not StockMovement.objects.filter(kind=MovementKind.SALE).exists()
    assert not BoxMovement.objects.filter(kind=BoxMovementKind.LEAVE).exists()
    assert boxes_held(organization, location=stocked_truck.location) == 5


def test_a_draft_keeps_its_boxes_until_it_is_confirmed(organization, stocked_truck, customer, dorade, driver, manager):
    api = client_for(driver)
    draft = sell(api, stocked_truck.location, customer, dorade, boxes={"small": 2}, confirm=False).json()

    assert not BoxMovement.objects.filter(kind=BoxMovementKind.LEAVE).exists()
    confirmed = client_for(manager).post(reverse("sale-confirm", args=[draft["id"]]), {}, format="json")

    assert confirmed.status_code == 200
    assert boxes_held(organization, customer=customer) == 2


def test_cancelling_a_sale_brings_its_boxes_back(organization, stocked_truck, customer, dorade, driver, manager):
    sold = sell(client_for(driver), stocked_truck.location, customer, dorade, boxes={"small": 3}).json()

    cancelled = client_for(manager).post(reverse("sale-cancel", args=[sold["id"]]), {"reason": "Erreur"}, format="json")

    assert cancelled.status_code == 200
    assert boxes_held(organization, customer=customer) == 0
    assert boxes_held(organization, location=stocked_truck.location) == 5


def test_a_sale_cannot_be_cancelled_when_the_client_already_gave_its_boxes_back(
    organization, stocked_truck, customer, dorade, driver, manager
):
    sold = sell(client_for(driver), stocked_truck.location, customer, dorade, boxes={"small": 3}).json()
    client_for(driver).post(reverse("my-box-pickups"), {"customer": customer.pk, "boxes": {"small": 3}}, format="json")

    cancelled = client_for(manager).post(reverse("sale-cancel", args=[sold["id"]]), {"reason": "Erreur"}, format="json")

    assert cancelled.status_code == 400
    assert Sale.objects.get().status == "confirmed"
    # The kilos did not come back either: the cancellation is refused as a whole.
    assert StockMovement.objects.filter(kind=MovementKind.CUSTOMER_RETURN).count() == 0
    assert boxes_held(organization, location=stocked_truck.location) == 5


# ---- Pickup visit ----


def test_a_driver_collects_boxes_from_a_client_onto_the_truck(organization, stocked_truck, customer, dorade, driver):
    api = client_for(driver)
    sell(api, stocked_truck.location, customer, dorade, boxes={"small": 3})

    response = api.post(reverse("my-box-pickups"), {"customer": customer.pk, "boxes": {"small": 2}}, format="json")

    assert response.status_code == 201
    assert boxes_held(organization, customer=customer) == 1
    assert boxes_held(organization, location=stocked_truck.location) == 4
    (collect,) = BoxMovement.objects.filter(kind=BoxMovementKind.COLLECT)
    assert (collect.box_type, collect.count) == ("small", 2)


def test_a_pickup_is_refused_when_the_client_holds_fewer_boxes(organization, stocked_truck, customer, dorade, driver):
    api = client_for(driver)
    sell(api, stocked_truck.location, customer, dorade, boxes={"small": 1})

    response = api.post(reverse("my-box-pickups"), {"customer": customer.pk, "boxes": {"small": 2}}, format="json")

    assert response.status_code == 400
    assert "Pas assez de petite caisse chez ce détenteur." in str(response.json())
    assert not BoxMovement.objects.filter(kind=BoxMovementKind.COLLECT).exists()
    assert boxes_held(organization, customer=customer) == 1


@pytest.mark.parametrize("boxes", [{}, {"small": 0, "big": 0}])
def test_a_pickup_needs_at_least_one_box(stocked_truck, customer, driver, boxes):
    response = client_for(driver).post(
        reverse("my-box-pickups"), {"customer": customer.pk, "boxes": boxes}, format="json"
    )

    assert response.status_code == 400
    assert "boxes" in response.json()


def test_a_pickup_refuses_an_unknown_box_type(stocked_truck, customer, driver):
    response = client_for(driver).post(
        reverse("my-box-pickups"), {"customer": customer.pk, "boxes": {"huge": 1}}, format="json"
    )

    assert response.status_code == 400
    assert response.json() == {"boxes.huge": "Type de caisse inconnu."}


def test_a_pickup_for_a_client_of_another_organization_is_refused(stocked_truck, driver):
    foreign = CustomerFactory.create(organization=OrganizationFactory.create(), name="Autre client")

    response = client_for(driver).post(
        reverse("my-box-pickups"), {"customer": foreign.pk, "boxes": {"small": 1}}, format="json"
    )

    assert response.status_code == 400
    assert "customer" in response.json()


def test_a_driver_without_a_truck_cannot_collect(organization, customer):
    lone = MembershipFactory.create(role=Role.DRIVER, organization=organization)

    response = client_for(lone).post(
        reverse("my-box-pickups"), {"customer": customer.pk, "boxes": {"small": 1}}, format="json"
    )

    assert response.status_code == 400


# ---- Day view ----


def test_the_day_view_shows_loaded_left_collected_and_expected(organization, stocked_truck, customer, dorade, driver):
    api = client_for(driver)
    sell(api, stocked_truck.location, customer, dorade, boxes={"small": 3})
    api.post(reverse("my-box-pickups"), {"customer": customer.pk, "boxes": {"small": 1}}, format="json")

    day = api.get(reverse("my-boxes"))

    assert day.status_code == 200
    body = day.json()
    assert body["truck_name"] == "Camion 1"
    lines = {line["box_type"]: line for line in body["lines"]}
    assert (lines["small"]["loaded"], lines["small"]["left"], lines["small"]["collected"]) == (5, 3, 1)
    assert lines["small"]["expected"] == 3
    assert (lines["big"]["loaded"], lines["big"]["left"], lines["big"]["collected"], lines["big"]["expected"]) == (
        2,
        0,
        0,
        2,
    )


def test_the_day_view_is_refused_to_the_office_and_to_a_driver_without_a_truck(organization, manager, driver):
    lone = MembershipFactory.create(role=Role.DRIVER, organization=organization)

    assert client_for(manager).get(reverse("my-boxes")).status_code == 403
    assert client_for(manager).post(reverse("my-box-pickups"), {}, format="json").status_code == 403
    assert client_for(lone).get(reverse("my-boxes")).status_code == 404


def test_only_drivers_see_the_day_view_and_collect(organization, manager, customer):
    accountant = MembershipFactory.create(role=Role.ACCOUNTANT, organization=organization)
    payload = {"customer": customer.pk, "boxes": {"small": 1}}

    assert client_for(accountant).get(reverse("my-boxes")).status_code == 403
    assert client_for(accountant).post(reverse("my-box-pickups"), payload, format="json").status_code == 403
    assert client_for(manager).post(reverse("my-box-pickups"), payload, format="json").status_code == 403


def test_anonymous_callers_get_401():
    assert APIClient().get(reverse("my-boxes")).status_code == 401
    assert APIClient().post(reverse("my-box-pickups"), {}, format="json").status_code == 401


def test_the_day_view_expects_the_boxes_the_truck_still_holds_from_earlier_days(
    stocked_truck, customer, dorade, driver
):
    for movement in BoxMovement.objects.filter(kind=BoxMovementKind.LOAD):
        backdate(movement, days=1)  # loaded yesterday
    api = client_for(driver)
    sell(api, stocked_truck.location, customer, dorade, boxes={"small": 3})

    lines = {line["box_type"]: line for line in api.get(reverse("my-boxes")).json()["lines"]}

    assert (lines["small"]["loaded"], lines["small"]["left"], lines["small"]["collected"]) == (0, 3, 0)
    assert lines["small"]["expected"] == 2  # 5 loaded yesterday, 3 left with the client today
    assert lines["big"]["expected"] == 2  # nothing moved today, 2 still on the truck


# ---- Offline retries (P1-T14e, D-124): the same client_uuid never makes two records ----


def test_a_pickup_sent_twice_with_the_same_client_uuid_is_posted_once(
    organization, stocked_truck, customer, dorade, driver
):
    api = client_for(driver)
    sell(api, stocked_truck.location, customer, dorade, boxes={"small": 3})
    payload = {"customer": customer.pk, "boxes": {"small": 2}, "client_uuid": str(uuid.uuid4())}

    first = api.post(reverse("my-box-pickups"), payload, format="json")
    second = api.post(reverse("my-box-pickups"), payload, format="json")

    assert (first.status_code, second.status_code) == (201, 201)
    assert BoxPickup.objects.for_organization(organization).count() == 1
    assert BoxMovement.objects.filter(kind=BoxMovementKind.COLLECT).count() == 1
    assert boxes_held(organization, customer=customer) == 1
    assert boxes_held(organization, location=stocked_truck.location) == 4


def test_a_refused_pickup_is_not_remembered_so_a_corrected_retry_posts(
    organization, stocked_truck, customer, dorade, driver
):
    api = client_for(driver)
    sell(api, stocked_truck.location, customer, dorade, boxes={"small": 1})
    payload = {"customer": customer.pk, "boxes": {"small": 2}, "client_uuid": str(uuid.uuid4())}

    refused = api.post(reverse("my-box-pickups"), payload, format="json")
    assert refused.status_code == 400
    assert not BoxPickup.objects.for_organization(organization).exists()

    payload["boxes"] = {"small": 1}
    assert api.post(reverse("my-box-pickups"), payload, format="json").status_code == 201
    assert boxes_held(organization, customer=customer) == 0


def test_a_sale_with_boxes_sent_twice_posts_its_boxes_once(organization, stocked_truck, customer, dorade, driver):
    api = client_for(driver)
    body = {
        "location": stocked_truck.location.pk,
        "customer": customer.pk,
        "lines": [{"product": dorade.pk, "quantity": "2"}],
        "amount_paid": "84.000",
        "payment_method": "cash",
        "confirm_now": True,
        "client_uuid": str(uuid.uuid4()),
        "boxes": {"small": 3},
    }

    first = api.post(reverse("sale-list"), body, format="json")
    second = api.post(reverse("sale-list"), body, format="json")

    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["id"] == second.json()["id"]
    assert BoxMovement.objects.filter(kind=BoxMovementKind.LEAVE).count() == 1
    assert boxes_held(organization, customer=customer) == 3
    assert boxes_held(organization, location=stocked_truck.location) == 2
