from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.models import OrganizationScopedModel, TimeStampedModel
from apps.core.money import MoneyField, QuantityField, line_total


class GoodsReceipt(OrganizationScopedModel, TimeStampedModel):
    """Goods received from a supplier on one day into one location, with their real net weight (Q12).

    Saving it creates one batch per line and posts the receipt movements (P1-T07). A receipt is never
    edited afterwards: a mistake is corrected by a supplier return or an adjustment (ARCHITECTURE §4.5).
    """

    # "BR-0001", "BR-0002"... per organization, given by `services.create_receipt`.
    number = models.CharField(max_length=20)
    # By name, not by import: an app only uses another app's services and selectors (ARCHITECTURE §3).
    supplier = models.ForeignKey("partners.Supplier", on_delete=models.PROTECT, related_name="receipts")
    location = models.ForeignKey("inventory.StockLocation", on_delete=models.PROTECT, related_name="receipts")
    received_on = models.DateField()
    # The supplier's delivery note or invoice number, as printed on their paper.
    supplier_reference = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["-received_on", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "number"], name="receipt_number_unique_per_organization"),
        ]

    def __str__(self) -> str:
        return self.number


class GoodsReceiptLine(OrganizationScopedModel):
    """One product of a receipt: what was ordered, what the supplier invoices, what was accepted.

    Weights are net (Q12): no gross weight or ice glaze. The accepted weight enters stock as a new batch
    at the line's cost; the invoiced weight is what the supplier will charge (P1-T08).
    """

    receipt = models.ForeignKey(GoodsReceipt, on_delete=models.PROTECT, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    batch = models.OneToOneField("inventory.Batch", on_delete=models.PROTECT, related_name="receipt_line")
    # Empty when nothing was ordered beforehand (the boat came in with what it had).
    # A QuantityField that may be empty (QuantityField itself is typed as never empty).
    ordered_quantity = models.DecimalField[Decimal | None, Decimal | None](
        max_digits=12, decimal_places=3, null=True, blank=True
    )
    invoiced_quantity = QuantityField()
    accepted_quantity = QuantityField()
    # DT per kg without VAT, typed on every receipt: purchase prices change daily (D-020).
    unit_cost = MoneyField()

    class Meta:
        ordering = ["receipt", "id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(accepted_quantity__gt=0), name="receipt_line_accepted_positive"),
            models.CheckConstraint(condition=models.Q(invoiced_quantity__gt=0), name="receipt_line_invoiced_positive"),
            models.CheckConstraint(
                condition=models.Q(ordered_quantity__isnull=True) | models.Q(ordered_quantity__gt=0),
                name="receipt_line_ordered_positive",
            ),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="receipt_line_cost_not_negative"),
        ]

    def __str__(self) -> str:
        return f"{self.receipt} · {self.batch}"

    @property
    def invoiced_amount(self) -> Decimal:
        """What the supplier charges for this line: invoiced weight × cost."""
        return line_total(self.invoiced_quantity, self.unit_cost)

    @property
    def accepted_amount(self) -> Decimal:
        """Value of what entered stock: accepted weight × cost."""
        return line_total(self.accepted_quantity, self.unit_cost)

    @property
    def has_difference(self) -> bool:
        """Accepted weight differs from the invoiced weight, or from the ordered weight when there was an order."""
        ordered_differs = self.ordered_quantity is not None and self.ordered_quantity != self.accepted_quantity
        return self.invoiced_quantity != self.accepted_quantity or ordered_differs


class ReceiptCounter(OrganizationScopedModel):
    """The last receipt number given in an organization, locked while a number is taken."""

    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization"], name="one_receipt_counter_per_organization")]

    def __str__(self) -> str:
        return f"{self.organization} · {self.last_number}"
