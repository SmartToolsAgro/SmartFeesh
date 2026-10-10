import datetime as dt
import threading
import uuid
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone

from apps.catalog.tests.factories import ProductFactory
from apps.core.tests.factories import OrganizationFactory, UserFactory
from apps.inventory import selectors, services
from apps.inventory.models import LocationKind, MovementKind, StockMovement

from .factories import BatchFactory, StockLocationFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def organization():
    return OrganizationFactory.create()


@pytest.fixture
def actor():
    return UserFactory.create()


@pytest.fixture
def cold_room(organization):
    return StockLocationFactory.create(organization=organization, name="Chambre froide 1")


@pytest.fixture
def truck(organization):
    return StockLocationFactory.create(organization=organization, kind=LocationKind.TRUCK, name="Camion 1")


@pytest.fixture
def product(organization):
    return ProductFactory.create(organization=organization, name="Crevette Royale")


def receive(organization, product, location, kg, *, days_ago=0):
    batch = BatchFactory.create(
        organization=organization, product=product, received_on=timezone.localdate() - dt.timedelta(days=days_ago)
    )
    services.post_movement(
        organization=organization, actor=None, kind=MovementKind.RECEIPT, batch=batch, quantity=kg, to_location=location
    )
    return batch


def take(organization, actor, product, quantity, from_location, **fields):
    return services.post_fifo_movements(
        organization=organization,
        actor=actor,
        product_id=product.pk,
        quantity=quantity,
        from_location=from_location,
        **{"kind": MovementKind.TRANSFER, **fields},
    )


def split(movements):
    return [(movement.batch, movement.quantity) for movement in movements]


def test_the_oldest_batch_is_emptied_before_the_next(organization, actor, product, cold_room, truck):
    recent = receive(organization, product, cold_room, "20", days_ago=1)
    old = receive(organization, product, cold_room, "10", days_ago=3)

    movements = take(organization, actor, product, "15", cold_room, to_location=truck)

    assert split(movements) == [(old, Decimal("10.000")), (recent, Decimal("5.000"))]
    assert selectors.quantity_on_hand(organization, location_id=cold_room.pk) == Decimal("15.000")
    assert selectors.quantity_on_hand(organization, location_id=truck.pk) == Decimal("15.000")


def test_batches_received_the_same_day_leave_in_receipt_order(organization, actor, product, cold_room):
    first = receive(organization, product, cold_room, "4")
    second = receive(organization, product, cold_room, "4")

    movements = take(organization, actor, product, "5", cold_room, kind=MovementKind.SALE)

    assert split(movements) == [(first, Decimal("4.000")), (second, Decimal("1.000"))]


def test_the_preview_gives_the_same_split_without_posting(organization, actor, product, cold_room, truck):
    old = receive(organization, product, cold_room, "10", days_ago=2)
    recent = receive(organization, product, cold_room, "10")

    preview = selectors.allocate_fifo(organization, product_id=product.pk, location=cold_room, quantity="12.5")

    assert preview == [(old, Decimal("10.000")), (recent, Decimal("2.500"))]
    assert not StockMovement.objects.exclude(kind=MovementKind.RECEIPT).exists()
    assert split(take(organization, actor, product, "12.5", cold_room, to_location=truck)) == preview


def test_more_than_the_location_holds_is_refused_as_a_whole(organization, actor, product, cold_room, truck):
    receive(organization, product, cold_room, "10", days_ago=1)
    receive(organization, product, cold_room, "5")
    receive(organization, product, truck, "50")  # another location's stock does not count

    with pytest.raises(ValidationError) as caught:
        take(organization, actor, product, "15.5", cold_room, to_location=truck)
    assert "15.000 kg" in caught.value.message_dict["quantity"][0]

    with pytest.raises(ValidationError):
        selectors.allocate_fifo(organization, product_id=product.pk, location=cold_room, quantity="15.5")
    assert selectors.quantity_on_hand(organization, location_id=cold_room.pk) == Decimal("15.000")
    assert StockMovement.objects.count() == 3


def test_only_the_product_asked_is_taken(organization, actor, product, cold_room):
    receive(organization, ProductFactory.create(organization=organization), cold_room, "30")
    mine = receive(organization, product, cold_room, "3")

    assert split(take(organization, actor, product, "3", cold_room, kind=MovementKind.SALE)) == [
        (mine, Decimal("3.000"))
    ]


def test_a_loss_taken_oldest_first_keeps_its_reason(organization, actor, product, truck):
    receive(organization, product, truck, "2")

    (loss,) = take(organization, actor, product, "1.5", truck, kind=MovementKind.LOSS, reason="Abîmé au transport")

    assert (loss.kind, loss.to_location, loss.reason, loss.user) == ("loss", None, "Abîmé au transport", actor)


def test_kinds_that_take_nothing_and_wrong_quantities_are_refused(organization, actor, product, cold_room):
    receive(organization, product, cold_room, "10")

    with pytest.raises(ValidationError) as caught:
        take(organization, actor, product, "1", cold_room, kind=MovementKind.RECEIPT)
    assert list(caught.value.message_dict) == ["kind"]
    with pytest.raises(ValidationError) as caught:
        take(organization, actor, product, "0", cold_room, kind=MovementKind.SALE)
    assert list(caught.value.message_dict) == ["quantity"]
    with pytest.raises(ValidationError) as caught:
        take(organization, actor, product, "1", StockLocationFactory.create(), kind=MovementKind.SALE)
    assert list(caught.value.message_dict) == ["from_location"]


def test_a_request_sent_twice_is_posted_once(organization, actor, product, cold_room, truck):
    receive(organization, product, cold_room, "5", days_ago=1)
    receive(organization, product, cold_room, "5")
    key = uuid.uuid4()

    first = take(organization, actor, product, "8", cold_room, to_location=truck, client_uuid=key)
    again = take(organization, actor, product, "8", cold_room, to_location=truck, client_uuid=key)

    assert again == first
    assert len(first) == 2
    assert selectors.quantity_on_hand(organization, location_id=truck.pk) == Decimal("8.000")


def run_at_once(count: int, action) -> list[Exception]:
    errors: list[Exception] = []
    start = threading.Barrier(count)

    def run() -> None:
        try:
            start.wait()
            action()
        except Exception as error:  # noqa: BLE001 - every failure is reported to the test
            errors.append(error)
        finally:
            connection.close()

    threads = [threading.Thread(target=run) for _ in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return errors


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_two_trucks_loaded_at_once_never_take_the_same_kilos():
    organization = OrganizationFactory.create()
    product = ProductFactory.create(organization=organization)
    cold_room = StockLocationFactory.create(organization=organization)
    trucks = iter([StockLocationFactory.create(organization=organization, kind=LocationKind.TRUCK) for _ in range(2)])
    receive(organization, product, cold_room, "6", days_ago=1)
    receive(organization, product, cold_room, "6")

    def load() -> None:
        take(organization, None, product, "7", cold_room, to_location=next(trucks))

    errors = run_at_once(2, load)

    assert len(errors) == 1
    assert isinstance(errors[0], ValidationError)
    assert selectors.quantity_on_hand(organization, location_id=cold_room.pk) == Decimal("5.000")


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_loads_and_returns_at_once_do_not_deadlock():
    organization = OrganizationFactory.create()
    product = ProductFactory.create(organization=organization)
    cold_room = StockLocationFactory.create(organization=organization)
    truck = StockLocationFactory.create(organization=organization, kind=LocationKind.TRUCK)
    for days_ago in (3, 2, 1):
        receive(organization, product, cold_room, "10", days_ago=days_ago)
        receive(organization, product, truck, "10", days_ago=days_ago)
    directions = iter([(cold_room, truck), (truck, cold_room)] * 4)

    def move() -> None:
        source, target = next(directions)
        # 4 × 7 kg out of each side is at most 28 of its 30 kg, whatever the order: only locks can fail here.
        take(organization, None, product, "7", source, to_location=target)

    assert run_at_once(8, move) == []
    total = selectors.quantity_on_hand(organization, product_id=product.pk)
    assert total == Decimal("60.000")
