from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import OrganizationScopedModel, TimeStampedModel


class TruckCondition(models.TextChoices):
    OK = "ok", _("En service")
    MAINTENANCE = "maintenance", _("En maintenance")
    BREAKDOWN = "breakdown", _("En panne")


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
    # A truck in maintenance or broken down cannot be taken by a driver (D-162).
    condition = models.CharField(max_length=12, choices=TruckCondition.choices, default=TruckCondition.OK)

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
    # Empty: the truck is left free that day, also for its usual driver (D-162).
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="truck_assignments"
    )
    date = models.DateField()

    class Meta:
        ordering = ["date", "truck__location__name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "truck", "date"], name="one_driver_per_truck_per_day"),
            models.UniqueConstraint(fields=["organization", "driver", "date"], name="one_truck_per_driver_per_day"),
        ]

    def __str__(self) -> str:
        return f"{self.date} · {self.truck.location.name} · {self.driver.username if self.driver else '-'}"


class DriverDay(OrganizationScopedModel, TimeStampedModel):
    """A driver's working day on a truck, opened from the phone with the cash float in hand (P3-T01).

    One per driver and date. Sending the closing ends it (D-134): it covers its date up to that moment
    (`selectors.day_window`) and takes nothing made after it, until a load validated that date opens it again.
    """

    truck = models.ForeignKey(Truck, on_delete=models.PROTECT, related_name="driver_days")
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="driver_days")
    date = models.DateField()
    # Cash the driver starts the day with (millimes).
    opening_cash = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    # Money the office gave for buying at the port, kept apart from the sales cash (D-158).
    purchase_float = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    # When the driver sent the closing; null while the day is running, and again once a new load reopened it.
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "driver", "date"], name="one_driver_day_per_driver_per_day"
            ),
            models.CheckConstraint(condition=models.Q(opening_cash__gte=0), name="driver_day_cash_not_negative"),
            models.CheckConstraint(
                condition=models.Q(purchase_float__gte=0), name="driver_day_purchase_float_not_negative"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.date} · {self.truck.location.name} · {self.driver.username}"
