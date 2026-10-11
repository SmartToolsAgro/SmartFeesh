from django.conf import settings
from django.db import models

from apps.core.models import OrganizationScopedModel, TimeStampedModel


class Truck(OrganizationScopedModel, TimeStampedModel):
    """A refrigerated truck and the driver who sells from it.

    Its stock lives in its own `inventory.StockLocation` (one to one), which also carries its name.
    """

    # By name, not by import: an app only uses another app's services and selectors (ARCHITECTURE §3).
    location = models.OneToOneField("inventory.StockLocation", on_delete=models.PROTECT, related_name="truck")
    # Tunisian plate as written on the truck, such as "123 TU 4567"; stored in capitals with single spaces.
    plate = models.CharField(max_length=20)
    # The usual driver: the default proposal and the fallback when nobody was assigned for the day (D-046).
    # Who drives it on a given date is a `TruckAssignment`; a driver may be the usual driver of several trucks.
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="trucks"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["location__name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "plate"], name="truck_plate_unique_per_organization"),
        ]

    def __str__(self) -> str:
        return f"{self.location.name} · {self.plate}"


class TruckAssignment(OrganizationScopedModel, TimeStampedModel):
    """Which driver takes which truck on a date (D-042, D-046).

    One driver per truck and one truck per driver each day. Phase 3's driver day builds on it.
    """

    truck = models.ForeignKey(Truck, on_delete=models.PROTECT, related_name="assignments")
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="truck_assignments")
    date = models.DateField()

    class Meta:
        ordering = ["date", "truck__location__name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "truck", "date"], name="one_driver_per_truck_per_day"),
            models.UniqueConstraint(fields=["organization", "driver", "date"], name="one_truck_per_driver_per_day"),
        ]

    def __str__(self) -> str:
        return f"{self.date} · {self.truck.location.name} · {self.driver.username}"
