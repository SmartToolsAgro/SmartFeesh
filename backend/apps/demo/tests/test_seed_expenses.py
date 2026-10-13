from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.core.models import Organization
from apps.expenses import selectors as expenses

pytestmark = pytest.mark.django_db

YEAR = timezone.localdate().year


def test_the_seed_records_expenses_labourers_and_days_worked(settings):
    settings.DEBUG = True

    call_command("seed_dev")
    call_command("seed_dev")  # running it again creates nothing

    organization = Organization.objects.get()
    rows = expenses.expenses_of(organization).filter(number__lte=f"DP-{YEAR}-0009").order_by("number")
    assert [(row.number, row.category.code, row.status, str(row.amount)) for row in rows] == [
        (f"DP-{YEAR}-0001", "fuel", "approved", "85.000"),
        (f"DP-{YEAR}-0002", "transport", "approved", "45.000"),
        (f"DP-{YEAR}-0003", "rent", "draft", "1200.000"),
        (f"DP-{YEAR}-0004", "accountant", "pending", "300.000"),
        (f"DP-{YEAR}-0005", "handling", "rejected", "18.500"),
        (f"DP-{YEAR}-0006", "day_labour", "approved", "40.000"),
        (f"DP-{YEAR}-0007", "day_labour", "approved", "35.000"),
        (f"DP-{YEAR}-0008", "day_labour", "draft", "45.000"),
        (f"DP-{YEAR}-0009", "day_labour", "draft", "40.000"),
    ]
    assert list(expenses.labourers_of(organization).values_list("name", flat=True)) == [
        "Ali Ben Salah",
        "Hichem Gharbi",
        "Moncef Trabelsi",
    ]
    # Camion 2's fuel is split over the lots of its morning load, to the millime.
    fuel = rows.get(number=f"DP-{YEAR}-0001")
    shares = expenses.truck_day_shares(organization, expenses=[fuel])[fuel.pk]
    assert len(shares) == 2
    assert sum(share.amount for share in shares) == Decimal("85.000")
    # The shrimp lot carries its transport, Ali's day and its share of the fuel.
    shrimp_lot = rows.get(number=f"DP-{YEAR}-0002").batch
    assert shrimp_lot is not None
    lines = expenses.lot_cost_lines(organization, batch_id=shrimp_lot.pk)
    assert {line.category_code for line in lines} >= {"transport", "day_labour"}
