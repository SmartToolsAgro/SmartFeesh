from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

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


class SupplierInvoiceStatus(models.TextChoices):
    # Typed but not checked yet: its receipts, dates and reference can still change, or it can be deleted.
    DRAFT = "draft", _("Brouillon")
    # Checked and owed: it no longer changes; only payments move it on.
    POSTED = "posted", _("Validée")
    PARTLY_PAID = "partly_paid", _("Payée en partie")
    PAID = "paid", _("Payée")


class SupplierInvoice(OrganizationScopedModel, TimeStampedModel):
    """What a supplier charges for one or more goods receipts: a trade payable (P1-T08, D-043).

    Its amount is the invoiced amount of its receipts (invoiced kg × cost, D-039), never typed. Once
    posted it is immutable; payments change its status only. A partner's capital and profit share are
    other balances (D-040) and never pass through it.
    """

    # "FF-0001", "FF-0002"... per organization, given by `services.create_invoice`.
    number = models.CharField(max_length=20)
    supplier = models.ForeignKey("partners.Supplier", on_delete=models.PROTECT, related_name="invoices")
    # The number printed on the supplier's invoice.
    supplier_reference = models.CharField(max_length=50, blank=True)
    invoice_date = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=SupplierInvoiceStatus.choices, default=SupplierInvoiceStatus.DRAFT)
    # The sum of its receipts' invoiced amounts, kept by the services; frozen once posted.
    total = MoneyField(default=Decimal("0.000"))
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["-invoice_date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "number"], name="invoice_number_unique_per_organization"),
            models.CheckConstraint(condition=models.Q(total__gte=0), name="invoice_total_not_negative"),
            models.CheckConstraint(
                condition=models.Q(due_date__gte=models.F("invoice_date")), name="invoice_due_after_invoice_date"
            ),
        ]

    def __str__(self) -> str:
        return self.number


class SupplierInvoiceReceipt(OrganizationScopedModel):
    """A goods receipt charged on an invoice. A receipt is on one invoice at most, draft or posted."""

    invoice = models.ForeignKey(SupplierInvoice, on_delete=models.CASCADE, related_name="receipt_links")
    receipt = models.OneToOneField(GoodsReceipt, on_delete=models.PROTECT, related_name="invoice_link")
    # The receipt's invoiced total when it was linked. Receipts never change, so neither does this.
    amount = MoneyField()

    class Meta:
        ordering = ["invoice", "receipt__received_on", "receipt_id"]
        constraints = [models.CheckConstraint(condition=models.Q(amount__gte=0), name="invoice_receipt_not_negative")]

    def __str__(self) -> str:
        return f"{self.invoice} · {self.receipt}"


class PaymentMethod(models.TextChoices):
    CASH = "cash", _("Espèces")
    CHEQUE = "cheque", _("Chèque")
    TRANSFER = "transfer", _("Virement")
    # "Traite": a bill of exchange, common between Tunisian businesses.
    BILL = "bill", _("Traite")
    OTHER = "other", _("Autre")


class SupplierPayment(OrganizationScopedModel, TimeStampedModel):
    """Money paid to a supplier, allocated to their posted invoices: all of it, part of it or none (D-043).

    The part not allocated yet is an advance: it already lowers the supplier balance and can be allocated
    to a later invoice. A recorded payment is never edited.
    """

    # "RF-0001", "RF-0002"... per organization ("règlement fournisseur").
    number = models.CharField(max_length=20)
    supplier = models.ForeignKey("partners.Supplier", on_delete=models.PROTECT, related_name="payments")
    paid_on = models.DateField()
    amount = MoneyField()
    method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    # Cheque or bill number, transfer reference.
    reference = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["-paid_on", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "number"], name="payment_number_unique_per_organization"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="payment_amount_positive"),
        ]

    def __str__(self) -> str:
        return self.number


class SupplierPaymentAllocation(OrganizationScopedModel, TimeStampedModel):
    """The part of a payment that settles one invoice: given with the payment, or later for an advance."""

    payment = models.ForeignKey(SupplierPayment, on_delete=models.PROTECT, related_name="allocations")
    invoice = models.ForeignKey(SupplierInvoice, on_delete=models.PROTECT, related_name="allocations")
    amount = MoneyField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["payment", "id"]
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="allocation_amount_positive")]

    def __str__(self) -> str:
        return f"{self.payment} → {self.invoice}"


class DocumentKind(models.TextChoices):
    SUPPLIER_INVOICE = "supplier_invoice", _("Facture fournisseur")
    SUPPLIER_PAYMENT = "supplier_payment", _("Paiement fournisseur")


class DocumentCounter(OrganizationScopedModel):
    """The last number given to one kind of purchasing document in an organization, locked while taken."""

    kind = models.CharField(max_length=30, choices=DocumentKind.choices)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "kind"], name="one_document_counter_per_kind"),
        ]

    def __str__(self) -> str:
        return f"{self.organization} · {self.kind} · {self.last_number}"
