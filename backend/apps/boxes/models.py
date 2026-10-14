"""Returnable boxes ("caisses"): a count ledger in whole units, separate from kg stock (D-122).

Boxes are never products: they do not touch `StockOnHand`, kilos, FIFO or lots, carry no money and no tare.
A holder is a stock location (cold room, truck), a client or a supplier. Each holder has one `BoxHolder`
row, which is the key that balances and locks hang on.
"""

from typing import Any

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import OrganizationScopedModel, OrganizationScopedQuerySet, TimeStampedModel


class BoxType(models.TextChoices):
    SMALL = "small", _("Petite caisse")
    BIG = "big", _("Grande caisse")


class BoxMovementKind(models.TextChoices):
    # Boxes the company already owned when the ledger started: they enter a location from outside it (D-135).
    OPENING = "opening", _("Stock initial")
    RECEIVE = "receive", _("Réception fournisseur")
    LOAD = "load", _("Chargement camion")
    LEAVE = "leave", _("Départ chez client")
    COLLECT = "collect", _("Reprise chez client")
    RETURN = "return", _("Retour fournisseur")
    # A truck gives its boxes back to a cold room, with a stock transfer (P1-T14e, D-124).
    TRUCK_RETURN = "truck_return", _("Retour du camion en chambre froide")
    WRITE_OFF = "write_off", _("Casse ou perte")


class BoxHolder(OrganizationScopedModel, TimeStampedModel):
    """The identity of one holder of boxes: exactly one of a location, a client or a supplier is set."""

    location = models.ForeignKey(
        "inventory.StockLocation", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    customer = models.ForeignKey("partners.Customer", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    supplier = models.ForeignKey("partners.Supplier", null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(location__isnull=False, customer__isnull=True, supplier__isnull=True)
                    | models.Q(location__isnull=True, customer__isnull=False, supplier__isnull=True)
                    | models.Q(location__isnull=True, customer__isnull=True, supplier__isnull=False)
                ),
                name="box_holder_has_exactly_one_target",
            ),
            models.UniqueConstraint(
                fields=["organization", "location"],
                condition=models.Q(location__isnull=False),
                name="box_holder_location_unique_per_organization",
            ),
            models.UniqueConstraint(
                fields=["organization", "customer"],
                condition=models.Q(customer__isnull=False),
                name="box_holder_customer_unique_per_organization",
            ),
            models.UniqueConstraint(
                fields=["organization", "supplier"],
                condition=models.Q(supplier__isnull=False),
                name="box_holder_supplier_unique_per_organization",
            ),
        ]

    @property
    def target_kind(self) -> str:
        if self.location_id is not None:
            return "location"
        if self.customer_id is not None:
            return "customer"
        return "supplier"

    def __str__(self) -> str:
        return f"{self.organization} · {self.target_kind} {self.location_id or self.customer_id or self.supplier_id}"


class BoxPickup(OrganizationScopedModel):
    """One pickup visit: the boxes a client hands back to a truck (D-122). Its movements name it as their source.

    `client_uuid` is sent by the driver app: a retry of the same visit returns the pickup already posted.
    """

    customer = models.ForeignKey("partners.Customer", on_delete=models.PROTECT, related_name="+")
    location = models.ForeignKey("inventory.StockLocation", on_delete=models.PROTECT, related_name="+")
    client_uuid = models.UUIDField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "client_uuid"],
                condition=models.Q(client_uuid__isnull=False),
                name="box_pickup_client_uuid_unique_per_organization",
            ),
        ]

    def __str__(self) -> str:
        return f"Reprise · {self.customer_id} · {self.location_id}"


class BoxMovementQuerySet(OrganizationScopedQuerySet["BoxMovement"]):
    def update(self, **kwargs: Any) -> int:
        raise TypeError("Box movements are append-only: post a correcting movement instead")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise TypeError("Box movements are append-only: they are never deleted")


class BoxMovement(OrganizationScopedModel):
    """`count` boxes of one type moving from one holder to another (or out of the ledger on a write-off, or
    into it on an opening stock).

    Always positive; the holders give the direction. Append-only: a mistake is corrected by a new movement.
    Written only by `services.post_box_movement`.
    """

    box_type = models.CharField(max_length=10, choices=BoxType.choices)
    kind = models.CharField(max_length=12, choices=BoxMovementKind.choices)
    count = models.PositiveIntegerField()
    from_holder = models.ForeignKey(BoxHolder, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    to_holder = models.ForeignKey(BoxHolder, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    # Why a write-off happened (broken, lost). Required for a write-off, empty otherwise.
    reason = models.TextField(blank=True)
    # The document that caused it (delivery, receipt...), when there is one.
    source_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    source_id = models.PositiveBigIntegerField(null=True, blank=True)
    source = GenericForeignKey("source_type", "source_id")
    # Null when the system acts on its own.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now)

    objects = BoxMovementQuerySet.as_manager()  # type: ignore[misc]

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(count__gt=0), name="box_movement_count_positive"),
            models.CheckConstraint(
                condition=models.Q(from_holder__isnull=False) | models.Q(to_holder__isnull=False),
                name="box_movement_has_a_holder",
            ),
            models.CheckConstraint(
                condition=~models.Q(kind="write_off") | ~models.Q(reason=""),
                name="box_write_off_has_a_reason",
            ),
        ]
        indexes = [models.Index(fields=["organization", "created_at"], name="box_movement_day_idx")]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} · {self.get_box_type_display()} · {self.count}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise TypeError("Box movements are append-only: post a correcting movement instead")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise TypeError("Box movements are append-only: they are never deleted")
