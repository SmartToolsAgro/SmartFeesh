"""Reusable read queries and unit helpers of the catalogue."""

from decimal import Decimal

from django.utils.translation import gettext as _

from apps.core.money import Number, quantity

from .models import KILOGRAM, Unit


def base_unit() -> Unit:
    """The unit every quantity is stored in. Always the kilogram for now (Q10)."""
    return Unit.objects.get(code=KILOGRAM)


def to_base_quantity(value: Number, unit: Unit) -> Decimal:
    """A quantity expressed in `unit`, converted to kg and rounded to grams, ready to be stored.

    Call it wherever a quantity enters the system, so that adding box or piece units later changes
    only this function. No conversion exists yet, so any unit other than kg is refused.
    """
    if unit.code != KILOGRAM:
        raise ValueError(
            _("Aucune conversion de « %(unit)s » vers %(base)s n'est définie.") % {"unit": unit.code, "base": KILOGRAM}
        )
    return quantity(value)
