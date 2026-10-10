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
    # The driver who uses it today. A driver has one truck at most; drivers see only their own truck.
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="trucks"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["location__name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "plate"], name="truck_plate_unique_per_organization"),
            models.UniqueConstraint(
                fields=["organization", "driver"],
                condition=models.Q(driver__isnull=False),
                name="one_truck_per_driver",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.location.name} · {self.plate}"
