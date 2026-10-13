"""Number and date formats of printed documents: 1 234,500 (a thin space between thousands, a comma)."""

import datetime as dt
from decimal import Decimal
from typing import Any

from django import template

from ..services import unique_identifier
from ..words import dinars_in_words

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


@register.filter
def quantity(value: Any) -> str:
    """A quantity without its unit and without trailing zeros, as in the Qté column: 90, 12,5, 1 097,9."""
    if value in (None, ""):
        return ""
    number = Decimal(str(value)).quantize(Decimal("0.001"))
    places = len(f"{number:f}".partition(".")[2].rstrip("0"))
    return _grouped(number, places)


@register.filter
def rate(value: Any) -> str:
    """A rate in a column with two decimals and no sign: 0,00, 19,00."""
    return "" if value in (None, "") else _grouped(value, 2)


@register.filter
def in_words(value: Any) -> str:
    """An amount in dinars in French words: Trois mille cinq cent quinze Dinars 500 Millimes."""
    return "" if value in (None, "") else dinars_in_words(Decimal(str(value)))


@register.filter
def one_line(value: Any) -> str:
    """Text typed on several lines (an address) on one line: "Route Mahdia KM4 - 3011 Sfax"."""
    return " - ".join(part.strip() for part in str(value or "").splitlines() if part.strip())


@register.filter
def unique_id(value: Any) -> str:
    """The "Identifiant unique" of a tax id (number and key letter), blank when it cannot be read."""
    return unique_identifier(str(value or ""))
