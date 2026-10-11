from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.core.models import Organization
from apps.inventory import selectors as inventory

pytestmark = pytest.mark.django_db


def test_the_seed_gives_camion_2_a_day_and_camion_3_a_load_to_validate(settings):
    settings.DEBUG = True

    call_command("seed_dev")
    call_command("seed_dev")  # running it again creates nothing

    organization = Organization.objects.get()
    transfers = inventory.transfers_of(organization)
    assert [(transfer.kind, transfer.status, transfer.to_location.name) for transfer in transfers] == [
        ("load", "draft", "Camion 3"),
        ("return", "validated", "Chambre froide 1 (frais)"),
        ("load", "validated", "Camion 2"),
    ]
    camion_2 = inventory.locations_of(organization).get(name="Camion 2")
    day = inventory.truck_day(organization, location_id=camion_2.pk, day=timezone.localdate())
    assert [(line.product_name, line.sold_or_lost, line.unit_price) for line in day] == [
        ("Crevette Royale", Decimal("7.000"), Decimal("42.000")),
        ("Dorade royale", Decimal("7.500"), Decimal("25.000")),
    ]
