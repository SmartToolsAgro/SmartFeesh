from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.core.models import Organization
from apps.expenses import cost_selectors
from apps.expenses.costing import add_months, first_of_month

pytestmark = pytest.mark.django_db


def test_the_seed_records_the_cold_room_cost_and_the_general_costs(settings):
    settings.DEBUG = True

    call_command("seed_dev")
    call_command("seed_dev")  # running it again creates nothing

    organization = Organization.objects.get()
    this_month = first_of_month(timezone.localdate())
    last_month = add_months(this_month, -1)
    bills = list(cost_selectors.bills_of(organization))
    assert [(bill.month, bill.expense.amount, bill.finalized_at is not None) for bill in bills] == [
        (last_month, Decimal("684.250"), True)
    ]
    last = cost_selectors.cold_room_month(organization, month=last_month)
    assert not last.estimated
    assert last.total == Decimal("684.250")
    assert sum((row.month_amount or Decimal("0") for row in last.rooms), Decimal("0")) == Decimal("684.250")
    assert {row.location_name: row.weight for row in last.rooms}["Chambre froide 2 (congelé)"] == Decimal("2.000")
    this = cost_selectors.cold_room_month(organization, month=this_month)
    assert this.estimated
    assert this.estimate_source_month == last_month
    assert [cost.name for cost in cost_selectors.recurring_costs_of(organization)] == [
        "Honoraires comptables",
        "Loyer du dépôt",
    ]
    periods = cost_selectors.general_periods_of(organization, month=this_month)
    assert sorted((period.expense.description, period.months) for period in periods) == [
        ("Assurance annuelle du dépôt", 12),
        ("Honoraires comptables", 1),
        ("Loyer du dépôt", 1),
    ]
