from django.db import models
from django.db.models.functions import Lower

from apps.core.models import OrganizationScopedModel, TimeStampedModel


class Supplier(OrganizationScopedModel, TimeStampedModel):
    """Someone the company buys seafood from: a fisherman, a wholesaler at the port, a fish farm, an importer.

    Its agreement (ordinary purchase, consignment, profit sharing, investment) comes in Phase 6; its
    balance comes with purchases and payments. Neither is stored here.
    """

    reference = models.CharField(max_length=30)
    name = models.CharField(max_length=150)
    # Tunisian "matricule fiscal", stored as 1234567A/A/M/000 (or 1234567A alone). Empty when unknown.
    tax_id = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    # Archived suppliers keep their history but cannot be bought from.
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                "organization", Lower("reference"), name="supplier_reference_unique_per_organization"
            ),
            models.UniqueConstraint(
                fields=["organization", "tax_id"],
                condition=~models.Q(tax_id=""),
                name="supplier_tax_id_unique_per_organization",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.reference} · {self.name}"


class SupplierContact(OrganizationScopedModel):
    """A person to call at a supplier: the boat owner, the accountant, the person who loads the goods."""

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=150)
    # What they do there ("Gérant", "Comptable"), free text.
    role = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)

    class Meta:
        ordering = ["supplier", "id"]

    def __str__(self) -> str:
        return f"{self.name} ({self.supplier.name})"
