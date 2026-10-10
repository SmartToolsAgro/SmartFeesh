from decimal import Decimal

import pytest
from django.db import IntegrityError

from apps.catalog import selectors
from apps.catalog.models import KILOGRAM, Unit

pytestmark = pytest.mark.django_db


def test_migrations_seed_the_kilogram_only():
    assert list(Unit.objects.values_list("code", "name", "symbol")) == [("kg", "Kilogramme", "kg")]


def test_the_base_unit_is_the_kilogram():
    assert selectors.base_unit().code == KILOGRAM


def test_unit_codes_are_unique():
    with pytest.raises(IntegrityError):
        Unit.objects.create(code=KILOGRAM, name="Doublon", symbol="kg")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("12.5", "12.500"),
        (3, "3.000"),
        (Decimal("0.0005"), "0.001"),  # a result finer than a gram rounds half up
    ],
)
def test_kilograms_are_stored_as_they_are_rounded_to_grams(value, expected):
    result = selectors.to_base_quantity(value, selectors.base_unit())

    assert result == Decimal(expected)
    assert result.as_tuple().exponent == -3


def test_a_unit_without_conversion_is_refused():
    box = Unit.objects.create(code="caisse", name="Caisse", symbol="caisse")

    with pytest.raises(ValueError, match="caisse"):
        selectors.to_base_quantity("2", box)


def test_floats_are_refused_before_any_conversion():
    with pytest.raises(TypeError):
        selectors.to_base_quantity(1.5, selectors.base_unit())  # type: ignore[arg-type]
