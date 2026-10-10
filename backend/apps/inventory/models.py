from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from apps.core.models import OrganizationScopedModel, TimeStampedModel


class LocationKind(models.TextChoices):
    COLD_ROOM = "cold_room", _("Chambre froide")
    TRUCK = "truck", _("Camion")
    OTHER = "other", _("Autre")


class StockLocation(OrganizationScopedModel, TimeStampedModel):
    """A place that holds stock: a cold room, a truck, or anything else (a freezer at a market stall).

    Every stock movement goes from one location to another (P1-T06). A truck's location is created and
    named with its `fleet.Truck`, never on its own.
    """

    kind = models.CharField(max_length=20, choices=LocationKind.choices)
    name = models.CharField(max_length=100)
    # Customers also buy at the counter of a cold room (Q8). Trucks always sell; this is for the others.
    counter_sales = models.BooleanField(default=False)
    # Archived locations keep their history but receive no more stock.
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "name", "id"]
        constraints = [
            models.UniqueConstraint("organization", Lower("name"), name="location_name_unique_per_organization"),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def sells(self) -> bool:
        """Whether sales may be made from here (P2-T04)."""
        return self.kind == LocationKind.TRUCK or self.counter_sales
