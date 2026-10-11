import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import OrganizationScopedModel


class DocumentKind(models.TextChoices):
    QUOTE = "quote", _("Devis")
    INVOICE = "invoice", _("Facture")
    CREDIT_NOTE = "credit_note", _("Avoir")
    RECEIPT = "receipt", _("Reçu de règlement")


def document_path(document: "GeneratedDocument", filename: str) -> str:
    # A random name: the address of a customer's document cannot be guessed (it is served by the API anyway).
    return f"documents/{document.organization_id}/{uuid.uuid4().hex}.pdf"


class GeneratedDocument(OrganizationScopedModel):
    """The PDF of one document (a quote, an invoice...), made by a background job and kept in the file storage.

    One row per document. `version` says which state of the document the file shows (its last change): when
    the document changes, the file is stale and made again on the next request (D-071). Issued invoices,
    credit notes and receipts hardly change, so their file is made once.
    """

    kind = models.CharField(max_length=20, choices=DocumentKind.choices)
    object_id = models.PositiveBigIntegerField()
    version = models.CharField(max_length=80, blank=True)
    file = models.FileField(upload_to=document_path, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    # When a job was last queued: a request that comes while it runs does not queue another.
    requested_at = models.DateTimeField(null=True, blank=True)
    # The reason the last job failed; empty when it worked.
    error = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "kind", "object_id"], name="one_pdf_per_document"),
        ]

    def __str__(self) -> str:
        return f"{self.kind} #{self.object_id}"
