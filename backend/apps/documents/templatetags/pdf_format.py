"""Number and date formats of printed documents: 1 234,500 (a thin space between thousands, a comma)."""

import datetime as dt
from decimal import Decimal
from typing import Any

from django import template

register = template.Library()

THIN_SPACE = " "


def _grouped(value: Any, places: int) -> str:
    number = Decimal(str(value)).quantize(Decimal(1).scaleb(-places))
    sign = "-" if number < 0 else ""
    whole, _dot, fraction = f"{abs(number):f}".partition(".")
    groups: list[str] = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    text = THIN_SPACE.join(groups)
    return f"{sign}{text},{fraction}" if places else f"{sign}{text}"


@register.filter
def money(value: Any) -> str:
    """An amount in dinars with three decimals (millimes): 1 234,500."""
    return "" if value in (None, "") else _grouped(value, 3)


@register.filter
def kilos(value: Any) -> str:
    """A weight with three decimals and its unit: 5,000 kg."""
    return "" if value in (None, "") else f"{_grouped(value, 3)} kg"


@register.filter
def percent(value: Any) -> str:
    """A rate: 19 % (decimals only when needed)."""
    if value in (None, ""):
        return ""
    number = Decimal(str(value))
    places = 0 if number == number.to_integral_value() else 2
    return f"{_grouped(number, places)} %"


@register.filter
def day(value: Any) -> str:
    """A date as 09/10/2026."""
    return value.strftime("%d/%m/%Y") if isinstance(value, dt.date) else ""


@register.filter
def isodate(value: Any) -> str:
    """A date kept as text in a frozen result (2026-10-09) as 09/10/2026."""
    if isinstance(value, dt.date):
        return value.strftime("%d/%m/%Y")
    try:
        return dt.date.fromisoformat(str(value)).strftime("%d/%m/%Y")
    except ValueError:
        return str(value)
