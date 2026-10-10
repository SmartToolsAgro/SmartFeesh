from django.db import models

from apps.core.models import TimeStampedModel

KILOGRAM = "kg"


class Unit(TimeStampedModel):
    """A unit of measure. Shared by every organization, like a currency code (D-029).

    Only the kilogram exists: everything is sold by kg (Q10) and quantities are stored in kg. The table
    keeps the door open for box or piece units that other distributors may need (Q17).
    """

    code = models.SlugField(max_length=20, unique=True)
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=10)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return self.symbol
