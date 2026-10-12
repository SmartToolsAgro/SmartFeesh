import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.tests.factories import ProductFactory
from apps.core.models import AuditLog, Role
from apps.core.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.inventory.models import StockMovement
from apps.inventory.tests.factories import StockLocationFactory
from apps.partners.tests.factories import SupplierFactory
from apps.purchasing import selectors, services
from apps.purchasing.models import GoodsReceipt, PurchaseOrderStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def organization():
    return OrganizationFactory.create()


@pytest.fixture
def actor():
    return UserFactory.create()


@pytest.fixture
def supplier(organization):
    return SupplierFactory.create(organization=organization, name="Mareyeur Port de Sfax")


@pytest.fixture
def cold_room(organization):
    return StockLocationFactory.create(organization=organization, name="Chambre froide 1")


@pytest.fixture
def dorade(organization):
    return ProductFactory.create(organization=organization, name="Dorade royale", reference="DO-003")


@pytest.fixture
def rouget(organization):
    return ProductFactory.create(organization=organization, name="Rouget", reference="RO-001")


def order_line(product, quantity="100", cost="20.000") -> dict[str, Any]:
    return {"product": product, "ordered_quantity": quantity, "unit_cost": cost}


def make_order(organization, actor, supplier, lines, **fields):
    values: dict[str, Any] = {"ordered_on": timezone.localdate()}
    values.update(fields)
    return services.create_order(organization=organization, actor=actor, supplier=supplier, lines=lines, **values)


def deliver(organization, actor, supplier, location, order, product, quantity, cost="20.000", **fields):
    values: dict[str, Any] = {
        "product": product,
        "invoiced_quantity": quantity,
        "accepted_quantity": quantity,
        "unit_cost": cost,
        **fields,
    }
    return services.create_receipt(
        organization=organization,
        actor=actor,
        supplier=supplier,
        location=location,
        purchase_order=order,
        received_on=timezone.localdate(),
        lines=[values],  # type: ignore[list-item]
    )


def reloaded(organization, order):
    return selectors.order_of(organization, order.pk)


# ---- creating ----


def test_an_order_is_numbered_and_moves_no_stock(organization, actor, supplier, dorade, rouget):
    order = make_order(organization, actor, supplier, [order_line(dorade), order_line(rouget, "40", "35.500")])
    second = make_order(organization, actor, supplier, [order_line(dorade)])

    assert (order.number, second.number) == ("BA-0001", "BA-0002")
    assert order.status == PurchaseOrderStatus.OPEN
    assert order.lines.count() == 2
    assert not StockMovement.objects.exists()
    assert AuditLog.objects.filter(action="purchase_order.created", target_id=order.pk).exists()


def test_an_order_with_problems_reports_them_all_at_once(organization, actor, supplier, dorade):
    other = ProductFactory.create(organization=OrganizationFactory.create())
    with pytest.raises(ValidationError) as failure:
        make_order(
            organization,
            actor,
            supplier,
            [
                order_line(dorade, "0"),
                order_line(dorade, "10", "abc"),
                order_line(other),
            ],
            ordered_on=timezone.localdate() + dt.timedelta(days=1),
            expected_on=timezone.localdate() - dt.timedelta(days=3),
        )
    errors = failure.value.message_dict
    assert {"ordered_on", "expected_on", "lines.0.ordered_quantity", "lines.1.unit_cost", "lines.2.product"} <= set(
        errors
    )
    assert "lines.1.product" in errors  # the same product twice
    assert not selectors.orders_of(organization).exists()


def test_an_order_needs_a_line(organization, actor, supplier):
    with pytest.raises(ValidationError) as failure:
        make_order(organization, actor, supplier, [])
    assert "lines" in failure.value.message_dict


# ---- partial receipts ----


def test_receipts_against_an_order_add_up_until_it_is_received(
    organization, actor, supplier, cold_room, dorade, rouget
):
    order = make_order(organization, actor, supplier, [order_line(dorade, "100"), order_line(rouget, "50")])

    first = deliver(organization, actor, supplier, cold_room, order, dorade, "60")
    order.refresh_from_db()
    assert order.status == PurchaseOrderStatus.PARTLY_RECEIVED
    assert first.purchase_order == order

    deliver(organization, actor, supplier, cold_room, order, dorade, "40")
    order.refresh_from_db()
    assert order.status == PurchaseOrderStatus.PARTLY_RECEIVED  # the rouget has not come

    deliver(organization, actor, supplier, cold_room, order, rouget, "50")
    order.refresh_from_db()
    assert order.status == PurchaseOrderStatus.RECEIVED

    lines = {line.product.reference: line for line in reloaded(organization, order).lines.all()}
    assert lines["DO-003"].received_quantity == Decimal("100.000")
    assert selectors.order_line_remaining(lines["DO-003"]) == Decimal("0.000")
    assert GoodsReceipt.objects.filter(purchase_order=order).count() == 3


def test_a_partial_delivery_shows_what_remains_and_is_not_a_difference(
    organization, actor, supplier, cold_room, dorade
):
    order = make_order(organization, actor, supplier, [order_line(dorade, "100")])
    receipt = deliver(organization, actor, supplier, cold_room, order, dorade, "30", ordered_quantity="100")

    (line,) = receipt.lines.all()
    assert line.ordered_quantity is None  # the order carries what was asked for
    assert not line.has_difference
    (order_line_,) = reloaded(organization, order).lines.all()
    assert order_line_.received_quantity == Decimal("30.000")
    assert selectors.order_line_remaining(order_line_) == Decimal("70.000")


def test_the_accepted_weight_is_what_counts_as_received(organization, actor, supplier, cold_room, dorade):
    order = make_order(organization, actor, supplier, [order_line(dorade, "100")])
    services.create_receipt(
        organization=organization,
        actor=actor,
        supplier=supplier,
        location=cold_room,
        purchase_order=order,
        received_on=timezone.localdate(),
        lines=[
            {"product": dorade, "invoiced_quantity": "100", "accepted_quantity": "95", "unit_cost": "20.000"},
        ],
    )
    order.refresh_from_db()
    assert order.status == PurchaseOrderStatus.PARTLY_RECEIVED


def test_more_than_ordered_still_completes_the_order(organization, actor, supplier, cold_room, dorade):
    order = make_order(organization, actor, supplier, [order_line(dorade, "100")])
    deliver(organization, actor, supplier, cold_room, order, dorade, "105")
    order.refresh_from_db()
    assert order.status == PurchaseOrderStatus.RECEIVED
    (line,) = reloaded(organization, order).lines.all()
    assert selectors.order_line_remaining(line) == Decimal("0.000")


def test_a_receipt_refuses_a_product_that_is_not_on_the_order(organization, actor, supplier, cold_room, dorade, rouget):
    order = make_order(organization, actor, supplier, [order_line(dorade)])
    with pytest.raises(ValidationError) as failure:
        deliver(organization, actor, supplier, cold_room, order, rouget, "10")
    assert "lines.0.product" in failure.value.message_dict
    assert not GoodsReceipt.objects.exists()


def test_a_receipt_refuses_an_order_of_another_supplier(organization, actor, supplier, cold_room, dorade):
    other = SupplierFactory.create(organization=organization)
    order = make_order(organization, actor, other, [order_line(dorade)])
    with pytest.raises(ValidationError) as failure:
        deliver(organization, actor, supplier, cold_room, order, dorade, "10")
    assert "purchase_order" in failure.value.message_dict


def test_a_receipt_without_an_order_still_works(organization, actor, supplier, cold_room, dorade):
    receipt = services.create_receipt(
        organization=organization,
        actor=actor,
        supplier=supplier,
        location=cold_room,
        received_on=timezone.localdate(),
        lines=[{"product": dorade, "invoiced_quantity": "5", "accepted_quantity": "5", "unit_cost": "20"}],
    )
    assert receipt.purchase_order is None


# ---- closing and cancelling ----


def test_a_partly_received_order_can_be_closed_and_then_takes_no_more_goods(
    organization, actor, supplier, cold_room, dorade
):
    order = make_order(organization, actor, supplier, [order_line(dorade, "100")])
    deliver(organization, actor, supplier, cold_room, order, dorade, "60")

    closed = services.close_order(order=order, actor=actor)

    assert closed.status == PurchaseOrderStatus.CLOSED
    assert closed.closed_at is not None
    with pytest.raises(ValidationError) as failure:
        deliver(organization, actor, supplier, cold_room, order, dorade, "10")
    assert "purchase_order" in failure.value.message_dict


def test_only_a_partly_received_order_can_be_closed(organization, actor, supplier, dorade):
    order = make_order(organization, actor, supplier, [order_line(dorade)])
    with pytest.raises(ValidationError):
        services.close_order(order=order, actor=actor)


def test_an_order_without_goods_can_be_cancelled_but_not_after(organization, actor, supplier, cold_room, dorade):
    untouched = make_order(organization, actor, supplier, [order_line(dorade)])
    started = make_order(organization, actor, supplier, [order_line(dorade)])
    deliver(organization, actor, supplier, cold_room, started, dorade, "10")

    assert services.cancel_order(order=untouched, actor=actor).status == PurchaseOrderStatus.CANCELLED
    with pytest.raises(ValidationError):
        services.cancel_order(order=started, actor=actor)
    with pytest.raises(ValidationError):
        services.cancel_order(order=untouched, actor=actor)


def test_pending_orders_are_the_ones_waiting_for_goods(organization, actor, supplier, cold_room, dorade):
    waiting = make_order(organization, actor, supplier, [order_line(dorade)])
    done = make_order(organization, actor, supplier, [order_line(dorade, "10")])
    deliver(organization, actor, supplier, cold_room, done, dorade, "10")
    cancelled = make_order(organization, actor, supplier, [order_line(dorade)])
    services.cancel_order(order=cancelled, actor=actor)

    pending = selectors.orders_of(organization, status="pending")
    assert [order.pk for order in pending] == [waiting.pk]


# ---- API ----


def api_client(organization, role=Role.OWNER) -> APIClient:
    membership = MembershipFactory.create(organization=organization, role=role)
    client = APIClient()
    client.force_authenticate(membership.user)
    return client


def test_the_api_creates_an_order_then_receives_it_in_two_deliveries(organization, supplier, cold_room, dorade, rouget):
    client = api_client(organization)
    created = client.post(
        reverse("purchase-order-list"),
        {
            "supplier": supplier.pk,
            "ordered_on": str(timezone.localdate()),
            "lines": [
                {"product": dorade.pk, "ordered_quantity": "100", "unit_cost": "20.000"},
                {"product": rouget.pk, "ordered_quantity": "40", "unit_cost": "35.000"},
            ],
        },
        format="json",
    )
    assert created.status_code == 201, created.content
    order_id = created.json()["id"]
    assert created.json()["number"] == "BA-0001"
    assert created.json()["ordered_total"] == "3400.000"

    def receive(product, quantity):
        return client.post(
            reverse("receipt-list"),
            {
                "supplier": supplier.pk,
                "location": cold_room.pk,
                "purchase_order": order_id,
                "received_on": str(timezone.localdate()),
                "lines": [
                    {
                        "product": product.pk,
                        "invoiced_quantity": quantity,
                        "accepted_quantity": quantity,
                        "unit_cost": "20.000",
                    }
                ],
            },
            format="json",
        )

    first = receive(dorade, "60")
    assert first.status_code == 201, first.content
    assert first.json()["purchase_order"]["number"] == "BA-0001"

    detail = client.get(reverse("purchase-order-detail", args=[order_id])).json()
    assert detail["status"] == "partly_received"
    by_product = {line["product"]["reference"]: line for line in detail["lines"]}
    assert by_product["DO-003"]["received_quantity"] == "60.000"
    assert by_product["DO-003"]["remaining_quantity"] == "40.000"
    assert by_product["RO-001"]["remaining_quantity"] == "40.000"
    assert len(detail["receipts"]) == 1

    assert receive(dorade, "40").status_code == 201
    assert receive(rouget, "40").status_code == 201
    done = client.get(reverse("purchase-order-detail", args=[order_id])).json()
    assert done["status"] == "received"

    listed = client.get(reverse("receipt-list"), {"purchase_order": order_id}).json()
    assert listed["count"] == 3


def test_the_api_closes_and_cancels(organization, actor, supplier, cold_room, dorade):
    client = api_client(organization)
    started = make_order(organization, actor, supplier, [order_line(dorade)])
    deliver(organization, actor, supplier, cold_room, started, dorade, "10")
    untouched = make_order(organization, actor, supplier, [order_line(dorade)])

    assert client.post(reverse("purchase-order-close", args=[started.pk])).json()["status"] == "closed"
    assert client.post(reverse("purchase-order-cancel", args=[untouched.pk])).json()["status"] == "cancelled"
    assert client.post(reverse("purchase-order-cancel", args=[started.pk])).status_code == 400


def test_the_api_follows_the_purchasing_permissions(organization, actor, supplier, dorade):
    order = make_order(organization, actor, supplier, [order_line(dorade)])
    body = {
        "supplier": supplier.pk,
        "ordered_on": str(timezone.localdate()),
        "lines": [{"product": dorade.pk, "ordered_quantity": "1", "unit_cost": "1"}],
    }

    accountant = api_client(organization, Role.ACCOUNTANT)
    assert accountant.get(reverse("purchase-order-list")).status_code == 200
    assert accountant.post(reverse("purchase-order-list"), body, format="json").status_code == 403
    assert accountant.post(reverse("purchase-order-cancel", args=[order.pk])).status_code == 403

    driver = api_client(organization, Role.DRIVER)
    assert driver.get(reverse("purchase-order-list")).status_code == 403

    anonymous = APIClient()
    assert anonymous.get(reverse("purchase-order-list")).status_code == 401


def test_orders_of_another_organization_are_invisible(organization, actor, supplier, dorade):
    order = make_order(organization, actor, supplier, [order_line(dorade)])
    stranger = api_client(OrganizationFactory.create())
    assert stranger.get(reverse("purchase-order-detail", args=[order.pk])).status_code == 404
    assert stranger.get(reverse("purchase-order-list")).json()["count"] == 0


def test_an_order_line_amount_too_big_to_store_is_refused(organization, actor, supplier, dorade):
    with pytest.raises(ValidationError) as failure:
        make_order(organization, actor, supplier, [order_line(dorade, "900000", "900000")])
    assert "lines.0.unit_cost" in failure.value.message_dict
