from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core.models import AuditLog
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
    return BatchFactory.create(organization=organization)


@pytest.fixture
def stocked(organization, actor, cold_room, truck, batch):
    """60 kg received, 15 kg loaded on the truck, 1.5 kg lost on the truck."""
    post = services.post_movement
    post(
        organization=organization,
        actor=actor,
        kind=MovementKind.RECEIPT,
        batch=batch,
        quantity="60",
        to_location=cold_room,
    )
    post(
        organization=organization,
        actor=actor,
        kind=MovementKind.TRANSFER,
        batch=batch,
        quantity="15",
        from_location=cold_room,
        to_location=truck,
    )
    post(
        organization=organization,
        actor=actor,
        kind=MovementKind.LOSS,
        batch=batch,
        quantity="1.5",
        from_location=truck,
        reason="Abîmé",
    )


def cached(location, batch) -> Decimal:
    return StockOnHand.objects.get(location=location, batch=batch).quantity


def test_the_cache_kept_by_post_movement_matches_the_ledger(organization, stocked):
    assert selectors.on_hand_differences(organization) == []


def test_a_damaged_cache_is_reported_then_repaired_from_the_ledger(
    organization, actor, cold_room, truck, batch, stocked
):
    StockOnHand.objects.filter(location=truck, batch=batch).update(quantity=Decimal("99.000"))

    differences = selectors.on_hand_differences(organization)
    assert [(d.location_id, d.cached, d.ledger) for d in differences] == [
        (truck.pk, Decimal("99.000"), Decimal("13.500"))
    ]

    repaired = services.rebuild_on_hand(organization=organization, actor=actor)

    assert repaired == differences
    assert (cached(cold_room, batch), cached(truck, batch)) == (Decimal("45.000"), Decimal("13.500"))
    assert selectors.on_hand_differences(organization) == []
    entry = AuditLog.objects.get(action="stock.on_hand_rebuilt")
    assert entry.actor == actor
    assert entry.after == {"rows": [{"location": truck.pk, "batch": batch.pk, "quantity": "13.500"}]}


def test_a_missing_row_is_recreated_and_a_row_without_movements_is_emptied(
    organization, actor, cold_room, truck, batch, stocked
):
    StockOnHand.objects.filter(location=cold_room, batch=batch).delete()
    stray = BatchFactory.create(organization=organization)
    StockOnHand.objects.create(
        organization=organization, location=truck, batch=stray, product=stray.product, quantity=Decimal("7")
    )

    assert len(selectors.on_hand_differences(organization)) == 2

    services.rebuild_on_hand(organization=organization, actor=actor)

    assert cached(cold_room, batch) == Decimal("45.000")
    assert cached(truck, stray) == Decimal("0.000")
    assert selectors.on_hand_differences(organization) == []


def test_nothing_to_repair_writes_nothing(organization, actor, stocked):
    assert services.rebuild_on_hand(organization=organization, actor=actor) == []
    assert not AuditLog.objects.filter(action="stock.on_hand_rebuilt").exists()


def test_another_organization_is_neither_reported_nor_touched(organization, actor, truck, batch, stocked):
    other = OrganizationFactory.create()
    StockOnHand.objects.filter(location=truck, batch=batch).update(quantity=Decimal("99.000"))

    assert selectors.on_hand_differences(other) == []
    services.rebuild_on_hand(organization=other, actor=actor)
    assert cached(truck, batch) == Decimal("99.000")


def test_a_ledger_that_would_go_below_zero_is_refused_not_repaired(organization, actor, truck, batch, stocked):
    # Only possible by writing to the database by hand: a movement taking more than was there.
    loss = StockMovement.objects.filter(kind=MovementKind.LOSS).get()
    StockMovement.objects.bulk_create(
        [
            StockMovement(
                organization=organization,
                kind=MovementKind.LOSS,
                product=loss.product,
                batch=batch,
                from_location=truck,
                quantity=Decimal("50"),
                unit_cost=loss.unit_cost,
                reason="Saisie directe",
            )
        ]
    )

    with pytest.raises(ValidationError, match="négatif"):
        services.rebuild_on_hand(organization=organization, actor=actor)
    assert cached(truck, batch) == Decimal("13.500")


def test_the_nightly_check_fails_on_a_difference_and_the_command_repairs_it(
    organization, truck, batch, stocked, capsys
):
    call_command("rebuild_on_hand", "--check")
    assert "0 difference(s) found" in capsys.readouterr().out

    StockOnHand.objects.filter(location=truck, batch=batch).update(quantity=Decimal("2.000"))
    with pytest.raises(CommandError, match="1 difference"):
        call_command("rebuild_on_hand", "--check")
    assert cached(truck, batch) == Decimal("2.000")

    call_command("rebuild_on_hand")
    assert "1 difference(s) repaired" in capsys.readouterr().out
    assert cached(truck, batch) == Decimal("13.500")
    call_command("rebuild_on_hand", "--check")
