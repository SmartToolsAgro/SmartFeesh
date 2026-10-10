import datetime as dt
import threading
import uuid
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone

from apps.core.tests.factories import OrganizationFactory, UserFactory
from apps.inventory import selectors, services
from apps.inventory.models import LocationKind, MovementKind, StockMovement, StockOnHand

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
def batch(organization):
    return BatchFactory.create(organization=organization, unit_cost=Decimal("20.000"))


def post(organization, actor, batch, kind, quantity, **fields):
    values: dict[str, Any] = {"kind": kind, "batch": batch, "quantity": quantity}
    values.update(fields)
    return services.post_movement(organization=organization, actor=actor, **values)


def held(organization, location, batch=None) -> Decimal:
    return selectors.quantity_on_hand(
        organization, location_id=location.pk, batch_id=batch.pk if batch is not None else None
    )


def test_a_receipt_a_transfer_and_a_loss_move_stock_between_locations(organization, actor, cold_room, truck, batch):
    post(organization, actor, batch, MovementKind.RECEIPT, "60", to_location=cold_room)
    post(organization, actor, batch, MovementKind.TRANSFER, "15", from_location=cold_room, to_location=truck)
    loss = post(organization, actor, batch, MovementKind.LOSS, "1.5", from_location=truck, reason="Abîmé")

    assert (held(organization, cold_room), held(organization, truck)) == (Decimal("45.000"), Decimal("13.500"))
    assert selectors.quantity_on_hand(organization, product_id=batch.product_id) == Decimal("58.500")
    assert (loss.product_id, loss.unit_cost, loss.user, loss.reason) == (
        batch.product_id,
        Decimal("20.000"),
        actor,
        "Abîmé",
    )
    assert [m.kind for m in selectors.movements_of(organization, location_id=truck.pk)] == ["loss", "transfer"]


def test_stock_never_goes_below_zero(organization, actor, cold_room, truck, batch):
    post(organization, actor, batch, MovementKind.RECEIPT, "10", to_location=cold_room)

    with pytest.raises(ValidationError) as caught:
        post(organization, actor, batch, MovementKind.TRANSFER, "10.001", from_location=cold_room, to_location=truck)

    assert list(caught.value.message_dict) == ["quantity"]
    assert "10.000 kg" in caught.value.message_dict["quantity"][0]
    assert held(organization, cold_room) == Decimal("10.000")
    assert not StockOnHand.objects.filter(location=truck).exists()
    assert StockMovement.objects.count() == 1


def test_each_kind_moves_only_on_its_own_side(organization, actor, cold_room, truck, batch):
    post(organization, actor, batch, MovementKind.RECEIPT, "20", to_location=cold_room)

    cases: list[tuple[str, dict[str, Any], str]] = [
        (MovementKind.RECEIPT, {"from_location": cold_room}, "from_location"),
        (MovementKind.SALE, {"to_location": truck}, "to_location"),
        (MovementKind.TRANSFER, {"from_location": cold_room}, "to_location"),
        (MovementKind.TRANSFER, {"from_location": cold_room, "to_location": cold_room}, "to_location"),
        (MovementKind.COUNT_CORRECTION, {"from_location": cold_room, "to_location": truck}, "to_location"),
        (MovementKind.COUNT_CORRECTION, {}, "to_location"),
    ]
    for kind, sides, field in cases:
        with pytest.raises(ValidationError) as caught:
            post(organization, actor, batch, kind, "1", **sides)
        assert field in caught.value.message_dict, (kind, sides)


def test_a_count_correction_or_an_adjustment_goes_either_way(organization, actor, cold_room, batch):
    post(organization, actor, batch, MovementKind.RECEIPT, "20", to_location=cold_room)
    post(organization, actor, batch, MovementKind.COUNT_CORRECTION, "0.4", from_location=cold_room)
    post(organization, actor, batch, MovementKind.ADJUSTMENT, "1", to_location=cold_room, reason="Erreur de pesée")

    assert held(organization, cold_room) == Decimal("20.600")


@pytest.mark.parametrize("kind", [MovementKind.LOSS, MovementKind.ADJUSTMENT])
def test_losses_and_adjustments_need_a_reason(organization, actor, cold_room, batch, kind):
    post(organization, actor, batch, MovementKind.RECEIPT, "20", to_location=cold_room)

    with pytest.raises(ValidationError) as caught:
        post(organization, actor, batch, kind, "1", from_location=cold_room, reason="  ")

    assert list(caught.value.message_dict) == ["reason"]


@pytest.mark.parametrize(
    ("quantity", "message"), [("0", "supérieure à zéro"), ("-2", "négative"), ("1.0001", "décimales")]
)
def test_quantities_are_checked_not_rounded(organization, actor, cold_room, batch, quantity, message):
    with pytest.raises(ValidationError) as caught:
        post(organization, actor, batch, MovementKind.RECEIPT, quantity, to_location=cold_room)

    assert message in caught.value.message_dict["quantity"][0]


def test_batches_and_locations_of_another_organization_or_archived_are_refused(organization, actor, cold_room, batch):
    elsewhere = StockLocationFactory.create()
    archived = StockLocationFactory.create(organization=organization, is_active=False)

    with pytest.raises(ValidationError) as caught:
        post(organization, actor, BatchFactory.create(), MovementKind.RECEIPT, "1", to_location=elsewhere)
    assert set(caught.value.message_dict) == {"batch", "to_location"}

    with pytest.raises(ValidationError) as caught:
        post(organization, actor, batch, MovementKind.RECEIPT, "1", to_location=archived)
    assert "archivé" in caught.value.message_dict["to_location"][0]


def test_the_same_client_uuid_posts_only_once(organization, actor, cold_room, batch):
    key = uuid.uuid4()
    first = post(organization, actor, batch, MovementKind.RECEIPT, "5", to_location=cold_room, client_uuid=key)
    again = post(organization, actor, batch, MovementKind.RECEIPT, "5", to_location=cold_room, client_uuid=key)

    assert again == first
    assert held(organization, cold_room) == Decimal("5.000")


def test_a_movement_keeps_its_source_document_and_when_it_happened(organization, actor, cold_room, batch):
    happened = timezone.now() - dt.timedelta(hours=3)

    movement = post(
        organization, actor, batch, MovementKind.RECEIPT, "5", to_location=cold_room, source=batch, occurred_at=happened
    )

    movement.refresh_from_db()
    assert (movement.source, movement.occurred_at) == (batch, happened)


def test_movements_are_never_changed_or_deleted(organization, actor, cold_room, batch):
    movement = post(organization, actor, batch, MovementKind.RECEIPT, "5", to_location=cold_room)

    movement.quantity = Decimal("50")
    with pytest.raises(TypeError):
        movement.save()
    with pytest.raises(TypeError):
        movement.delete()
    with pytest.raises(TypeError):
        StockMovement.objects.filter(pk=movement.pk).update(quantity=Decimal("50"))
    with pytest.raises(TypeError):
        StockMovement.objects.all().delete()


def test_a_location_holding_stock_cannot_be_archived(organization, actor, cold_room, truck, batch):
    post(organization, actor, batch, MovementKind.RECEIPT, "5", to_location=cold_room)

    with pytest.raises(ValidationError):
        services.set_location_active(location=cold_room, actor=actor, is_active=False)

    post(organization, actor, batch, MovementKind.TRANSFER, "5", from_location=cold_room, to_location=truck)
    assert services.set_location_active(location=cold_room, actor=actor, is_active=False).is_active is False


def test_on_hand_lists_only_what_is_held(organization, actor, cold_room, truck, batch):
    post(organization, actor, batch, MovementKind.RECEIPT, "5", to_location=cold_room)
    post(organization, actor, batch, MovementKind.TRANSFER, "5", from_location=cold_room, to_location=truck)

    assert [(row.location, row.quantity) for row in selectors.on_hand_of(organization)] == [(truck, Decimal("5.000"))]


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
def test_two_transfers_at_once_never_take_more_than_the_stock():
    organization = OrganizationFactory.create()
    cold_room = StockLocationFactory.create(organization=organization)
    trucks = [StockLocationFactory.create(organization=organization, kind=LocationKind.TRUCK) for _ in range(2)]
    batch = BatchFactory.create(organization=organization)
    post(organization, None, batch, MovementKind.RECEIPT, "10", to_location=cold_room)
    destinations = iter(trucks)

    def load_truck() -> None:
        post(
            organization,
            None,
            batch,
            MovementKind.TRANSFER,
            "7",
            from_location=cold_room,
            to_location=next(destinations),
        )

    errors = run_at_once(2, load_truck)

    assert len(errors) == 1
    assert isinstance(errors[0], ValidationError)
    assert held(organization, cold_room) == Decimal("3.000")
    assert sum(held(organization, truck) for truck in trucks) == Decimal("7.000")


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_crossed_transfers_at_once_do_not_deadlock():
    organization = OrganizationFactory.create()
    first, second = (StockLocationFactory.create(organization=organization) for _ in range(2))
    batch = BatchFactory.create(organization=organization)
    post(organization, None, batch, MovementKind.RECEIPT, "10", to_location=first)
    post(organization, None, batch, MovementKind.RECEIPT, "10", to_location=second)
    directions = iter([(first, second), (second, first)] * 4)

    def move() -> None:
        source, target = next(directions)
        post(organization, None, batch, MovementKind.TRANSFER, "1", from_location=source, to_location=target)

    assert run_at_once(8, move) == []
    assert held(organization, first) + held(organization, second) == Decimal("20.000")
