import pytest
from django.core.management import call_command

from apps.boxes import selectors as boxes
from apps.core.models import Organization
from apps.inventory import selectors as inventory

pytestmark = pytest.mark.django_db


def test_the_seed_puts_the_company_boxes_in_the_fresh_cold_room(settings):
    settings.DEBUG = True

    call_command("seed_dev")
    call_command("seed_dev")  # running it again creates nothing

    organization = Organization.objects.get()
    # 50 small and 50 big boxes the company owns (D-135): one holder, and no supplier is owed any.
    cold_room = inventory.locations_of(organization).get(name="Chambre froide 1 (frais)")
    assert [(row.holder.location, row.box_type, row.count) for row in boxes.balances_of(organization)] == [
        (cold_room, "big", 50),
        (cold_room, "small", 50),
    ]
    movements = boxes.movements_of(organization)
    assert sorted((movement.kind, movement.box_type, movement.count) for movement in movements) == [
        ("opening", "big", 50),
        ("opening", "small", 50),
    ]
    assert all(movement.from_holder is None for movement in movements)
