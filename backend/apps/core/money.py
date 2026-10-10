"""Amounts in Tunisian dinars and weights in kg: Decimal with 3 places, never floats (ARCHITECTURE §4.1-2).

Round only at defined points (a line total, a document total), with `money()` or `quantity()`.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import models

DECIMAL_PLACES = 3
MILLIME = Decimal("0.001")
GRAM = Decimal("0.001")

type Number = Decimal | int | str


def _to_decimal(value: Number) -> Decimal:
    # bool is an int subclass, and a float has already lost precision: both are programming errors here.
    if isinstance(value, bool) or not isinstance(value, Decimal | int | str):
        raise TypeError(f"Expected Decimal, int or str, got {type(value).__name__}: floats are never allowed")
    return Decimal(value)


def money(value: Number) -> Decimal:
    """Round an amount to millimes, half up."""
    return _to_decimal(value).quantize(MILLIME, rounding=ROUND_HALF_UP)


def quantity(value: Number) -> Decimal:
    """Round a weight to grams (3 decimals of a kg), half up."""
    return _to_decimal(value).quantize(GRAM, rounding=ROUND_HALF_UP)


def line_total(qty: Number, unit_price: Number) -> Decimal:
    """Amount of one document line: quantity × unit price, rounded once."""
    return money(_to_decimal(qty) * _to_decimal(unit_price))


class MoneyField(models.DecimalField[Decimal, Decimal]):
    """An amount in dinars: up to 99 999 999 999.999."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("max_digits", 14)
        kwargs.setdefault("decimal_places", DECIMAL_PLACES)
        super().__init__(*args, **kwargs)


class QuantityField(models.DecimalField[Decimal, Decimal]):
    """A quantity in the product's base unit (kg): up to 999 999 999.999."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("max_digits", 12)
        kwargs.setdefault("decimal_places", DECIMAL_PLACES)
        super().__init__(*args, **kwargs)
