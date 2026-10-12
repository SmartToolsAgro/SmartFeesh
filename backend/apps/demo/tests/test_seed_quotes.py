from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.core.models import Organization
from apps.sales import selectors as sales

pytestmark = pytest.mark.django_db

YEAR = timezone.localdate().year


def test_the_seed_gives_quotes_in_every_state_like_the_prototype(settings):
    settings.DEBUG = True

    call_command("seed_dev")
    call_command("seed_dev")  # running it again creates nothing

    organization = Organization.objects.get()
    quotes = {quote.customer.name: quote for quote in sales.quotes_of(organization)}
    assert {name: quote.current_status for name, quote in quotes.items()} == {  # type: ignore[attr-defined]
        "Restaurant Le Corail": "sent",
        "Hôtel Thyna": "sent",
        "Café-Resto Sidi Mansour": "accepted",
        "Poissonnerie El Bahr": "refused",
        "Supermarché Ennour": "draft",
    }
    corail = quotes["Restaurant Le Corail"]
    assert corail.number == f"DV-{YEAR}-0001"
    # The prototype's quote: 210.000 + 87.000 + 82.500 at the prices in force.
    assert [(line.product.reference, line.amount) for line in corail.lines.all()] == [
        ("CR-001", Decimal("210.000")),
        ("CA-005", Decimal("87.000")),
        ("SY-008", Decimal("82.500")),
    ]
    assert corail.total == Decimal("379.500")
