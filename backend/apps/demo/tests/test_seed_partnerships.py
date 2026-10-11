from decimal import Decimal

import pytest
from django.core.management import call_command

from apps.closing import selectors as closing
from apps.core.models import Organization
from apps.partnerships import selectors

pytestmark = pytest.mark.django_db


def test_the_seed_puts_the_seiche_lot_in_partnership_with_its_sale_and_cost(settings):
    settings.DEBUG = True

    call_command("seed_dev")
    call_command("seed_dev")  # running it again creates nothing

    organization = Organization.objects.get()
    (partnership,) = selectors.partnerships_of(organization)
    assert (partnership.partner.reference, partnership.batch.receipt_reference) == ("F-001", "KRK-1192")
    assert (partnership.profit_rate, partnership.loss_rate) == (Decimal("40.00"), Decimal("25.00"))
    assert selectors.capital_balance(partnership) == Decimal("107.500")

    result = closing.live_result(organization, batch_id=partnership.batch_id)
    # 4 kg sold on Sidi Mansour's converted quote, 18.000 of transport typed on the lot, 11 kg still in the
    # cold room. Its cold-room and general costs depend on the day the seed runs (kg-days up to today).
    assert result.quantity_sold == Decimal("4.000")
    assert result.cogs == Decimal("82.000")
    typed = next(group for group in result.cost_groups if group.kind == "lot")
    assert [(line.title, line.amount) for line in typed.lines] == [("Transport", Decimal("18.000"))]
    assert result.costs_total == sum((group.total for group in result.cost_groups), Decimal("0"))
    assert result.net_result == result.revenue - result.cogs - result.spoilage - result.costs_total
    assert result.snapshot.on_hand_quantity == Decimal("11.000")
    assert result.partner is not None
    assert result.partner.share + result.owner_share == result.net_result
