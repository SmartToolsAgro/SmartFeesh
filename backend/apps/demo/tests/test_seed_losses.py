import pytest
from django.core.management import call_command

from apps.core.models import Organization
from apps.inventory import selectors as inventory
from apps.inventory.models import StockCount, StockLocation, StockOnHand

pytestmark = pytest.mark.django_db


def test_the_seed_records_a_loss_one_waiting_and_opens_a_count(settings):
    settings.DEBUG = True

    call_command("seed_dev")
    call_command("seed_dev")  # running it again creates nothing

    organization = Organization.objects.get()
    losses = inventory.losses_of(organization).order_by("number")
    assert [(loss.number, loss.status, loss.product.reference, str(loss.quantity)) for loss in losses] == [
        ("PE-0001", "approved", "MO-007", "1.500"),
        ("PE-0002", "pending", "RO-009", "4.000"),
    ]
    (count,) = inventory.counts_of(organization)
    assert (count.number, count.status, count.location.name) == ("INV-0001", "counting", "Chambre froide 2 (congelé)")
    assert count.lines.count() > 0


def test_the_seed_runs_again_when_the_frozen_room_is_empty(settings):
    # Staging, 2026-10-14: the frozen room had been emptied by people using the demo, its count was gone, and the
    # seed failed every deploy on "nothing to count". The seed now leaves the count out.
    settings.DEBUG = True
    call_command("seed_dev")
    organization = Organization.objects.get()
    frozen_room = StockLocation.objects.get(organization=organization, name="Chambre froide 2 (congelé)")
    StockCount.objects.filter(location=frozen_room).delete()
    StockOnHand.objects.filter(location=frozen_room).delete()

    call_command("seed_dev")

    assert not inventory.counts_of(organization, location_id=frozen_room.pk).exists()
