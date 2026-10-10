from typing import Any

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import OrganizationScopedModel, OrganizationScopedQuerySet, TimeStampedModel
from apps.core.money import MoneyField, QuantityField


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


class MovementKind(models.TextChoices):
    RECEIPT = "receipt", _("Réception")
    TRANSFER = "transfer", _("Transfert")
    SALE = "sale", _("Vente")
    CUSTOMER_RETURN = "customer_return", _("Retour client")
    SUPPLIER_RETURN = "supplier_return", _("Retour fournisseur")
    LOSS = "loss", _("Perte")
    ADJUSTMENT = "adjustment", _("Ajustement")
    COUNT_CORRECTION = "count_correction", _("Correction d'inventaire")


class StockMovementQuerySet(OrganizationScopedQuerySet["StockMovement"]):
    def update(self, **kwargs: Any) -> int:
        raise TypeError("Stock movements are append-only: post a correcting movement instead")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise TypeError("Stock movements are append-only: they are never deleted")


class StockMovement(OrganizationScopedModel):
    """One quantity of one batch leaving a location, entering one, or going from one to another.

    The ledger is append-only (ARCHITECTURE §4.3, D-006): a mistake is corrected by a new movement.
    Stock on hand is the sum of the movements; `StockOnHand` only caches it. Written only by
    `services.post_movement`.
    """

    kind = models.CharField(max_length=20, choices=MovementKind.choices)
    # Always the batch's product, kept here so stock per product is read without a join.
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    batch = models.ForeignKey(Batch, on_delete=models.PROTECT, related_name="movements")
    # Empty on the outside side: a receipt has no `from`, a sale or a loss has no `to`.
    from_location = models.ForeignKey(
        StockLocation, null=True, blank=True, on_delete=models.PROTECT, related_name="movements_out"
    )
    to_location = models.ForeignKey(
        StockLocation, null=True, blank=True, on_delete=models.PROTECT, related_name="movements_in"
    )
    # Always positive, in kg; the locations give the direction.
    quantity = QuantityField()
    # Cost per kg of what moved: the batch's cost when posted, kept even if a later correction changes it.
    unit_cost = MoneyField()
    # The document that caused it (goods receipt, sale, count...), when there is one.
    source_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    source_id = models.PositiveBigIntegerField(null=True, blank=True)
    source = GenericForeignKey("source_type", "source_id")
    # Null when the system acts on its own.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    # When it happened (a driver offline may sync later); `created_at` is when it was posted.
    occurred_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True)
    # Sent by the driver app so a retried request never posts twice (ARCHITECTURE §4.7).
    client_uuid = models.UUIDField(null=True, blank=True)

    # mypy sees the base manager as a class variable; replacing it per model is the Django way.
    objects = StockMovementQuerySet.as_manager()  # type: ignore[misc]

    class Meta:
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="movement_quantity_positive"),
            models.CheckConstraint(
                condition=models.Q(from_location__isnull=False) | models.Q(to_location__isnull=False),
                name="movement_has_a_location",
            ),
            models.UniqueConstraint(
                fields=["organization", "client_uuid"],
                condition=models.Q(client_uuid__isnull=False),
                name="movement_client_uuid_unique_per_organization",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "product", "occurred_at"], name="movement_product_idx"),
            models.Index(fields=["source_type", "source_id"], name="movement_source_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} · {self.batch} · {self.quantity} kg"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise TypeError("Stock movements are append-only: post a correcting movement instead")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise TypeError("Stock movements are append-only: they are never deleted")


class StockOnHand(OrganizationScopedModel):
    """How many kg of one batch one location holds now: a cache of the movements, updated in the same
    transaction by `services.post_movement` and rebuilt from the ledger when in doubt (D-006)."""

    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="on_hand")
    batch = models.ForeignKey(Batch, on_delete=models.PROTECT, related_name="on_hand")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    quantity = QuantityField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["location", "batch"]
        constraints = [
            models.UniqueConstraint(fields=["location", "batch"], name="one_on_hand_row_per_location_and_batch"),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="on_hand_never_negative"),
        ]
        indexes = [models.Index(fields=["organization", "product"], name="on_hand_product_idx")]
        verbose_name_plural = "stock on hand"

    def __str__(self) -> str:
        return f"{self.location} · {self.batch} · {self.quantity} kg"
