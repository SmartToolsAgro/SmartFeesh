from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from apps.core.models import OrganizationScopedModel, TimeStampedModel
from apps.core.money import MoneyField


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


# Oldest batch first: by receipt date, then in the order they were received the same day (D-009, Q7).
FIFO_ORDER = ("received_on", "id")


class Batch(OrganizationScopedModel, TimeStampedModel):
    """A lot: one product delivered by one supplier on one day, at one cost per kg.

    Kilos of different batches never mix, so every kilo sold knows its supplier and its cost (D-009, Q4,
    Q7). How much of a batch is where comes from the stock ledger (P1-T06), and goods receipts create the
    batches (P1-T07). A batch is never edited once created: a mistake is corrected by a new document.
    """

    # "L-0001", "L-0002"... given by `services.create_batch`, never typed.
    number = models.CharField(max_length=20)
    # By name, not by import: an app only uses another app's services and selectors (ARCHITECTURE §3).
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="batches")
    supplier = models.ForeignKey("partners.Supplier", on_delete=models.PROTECT, related_name="batches")
    # The supplier's delivery note or invoice number, as printed on their paper. P1-T07 adds the receipt itself.
    receipt_reference = models.CharField(max_length=50, blank=True)
    received_on = models.DateField()
    # Purchase cost in DT per kg, without VAT. Costs change daily, so each batch carries its own (D-020).
    unit_cost = MoneyField()
    use_by = models.DateField(null=True, blank=True)

    class Meta:
        ordering = list(FIFO_ORDER)
        constraints = [
            models.UniqueConstraint(fields=["organization", "number"], name="batch_number_unique_per_organization"),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="batch_unit_cost_not_negative"),
        ]
        indexes = [models.Index(fields=["organization", "product", "received_on"], name="batch_fifo_idx")]
        verbose_name_plural = "batches"

    def __str__(self) -> str:
        return self.number


class BatchCounter(OrganizationScopedModel):
    """The last batch number given in an organization. Its row is locked while a number is taken, so two
    receipts saved at the same moment never get the same number."""

    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization"], name="one_batch_counter_per_organization")]

    def __str__(self) -> str:
        return f"{self.organization} · {self.last_number}"
