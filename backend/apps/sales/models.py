from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import OrganizationScopedModel, TimeStampedModel
from apps.core.money import MoneyField, QuantityField


class DocumentCounter(OrganizationScopedModel):
    """The last number given to one series of sales documents ("DV" quotes...) in an organization.

    Locked while a number is taken (same scheme as batches, D-034), so two documents saved at once never
    share one. Sales and invoices (P2-T04, P2-T05) take their own series here.
    """

    series = models.CharField(max_length=20)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "series"], name="sales_one_counter_per_series"),
        ]

    def __str__(self) -> str:
        return f"{self.organization} · {self.series} · {self.last_number}"


# ---- Quotes (P2-T03, D-050) ----


class QuoteStatus(models.TextChoices):
    # Being prepared: customer, dates, lines and prices may still change.
    DRAFT = "draft", _("Brouillon")
    # Given to the customer: frozen, waiting for the answer until its validity date.
    SENT = "sent", _("Envoyé")
    # The customer said yes before the validity date: ready to become a sale (P2-T04).
    ACCEPTED = "accepted", _("Accepté")
    # The customer said no.
    REFUSED = "refused", _("Refusé")
    # Sent, but its validity date passed without an answer.
    EXPIRED = "expired", _("Expiré")


class Quote(OrganizationScopedModel, TimeStampedModel):
    """A price offer to a customer: products, kg and prices, valid until a date.

    Its prices are kept on its lines, so later price changes never touch it (D-020). Only a draft
    changes; once sent it is frozen, and the customer's answer (accepted, refused) or its validity date
    (expired) closes it. An accepted quote becomes a sale in P2-T04. Nothing is reserved in the stock.
    """

    # "DV-0001", "DV-0002"... per organization, given by `services.create_quote`.
    number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=QuoteStatus.choices, default=QuoteStatus.DRAFT)
    # By name, not by import: an app only uses another app's services and selectors (ARCHITECTURE §3).
    customer = models.ForeignKey("partners.Customer", on_delete=models.PROTECT, related_name="quotes")
    # Where the goods would leave from (a cold room or a truck), if known. Information only: the stock it
    # holds is shown while typing, nothing is reserved; the sale (P2-T04) may start from it.
    location = models.ForeignKey(
        "inventory.StockLocation", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    quoted_on = models.DateField()
    # The last day the customer may accept (included).
    valid_until = models.DateField()
    notes = models.TextField(blank=True)
    # Totals are computed by the services from the lines and frozen with them.
    # Sum of kg × price of the lines, before discounts.
    subtotal = MoneyField(default=Decimal("0.000"))
    discount_total = MoneyField(default=Decimal("0.000"))
    # subtotal − discount_total: what the customer pays before VAT.
    total_excl_tax = MoneyField(default=Decimal("0.000"))
    # VAT hook (P2-T05): empty until the finance settings (rate, prices with or without VAT, D-018) exist.
    # Nothing computes it yet, so `total` is the amount without VAT.
    # A MoneyField that may be empty (MoneyField itself is typed as never empty).
    tax_amount = models.DecimalField[Decimal | None, Decimal | None](
        max_digits=14, decimal_places=3, null=True, blank=True
    )
    total = MoneyField(default=Decimal("0.000"))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    # Who recorded the customer's answer (accepted or refused), and when.
    answered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    answered_at = models.DateTimeField(null=True, blank=True)
    refusal_reason = models.CharField(max_length=255, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    # Sent by an app that may retry (the demo seed today): the same request never creates two quotes.
    client_uuid = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-quoted_on", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "number"], name="quote_number_unique_per_organization"),
            models.UniqueConstraint(
                fields=["organization", "client_uuid"],
                condition=models.Q(client_uuid__isnull=False),
                name="quote_client_uuid_unique_per_organization",
            ),
            models.CheckConstraint(
                condition=models.Q(valid_until__gte=models.F("quoted_on")), name="quote_valid_after_quote_date"
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0, discount_total__gte=0, total_excl_tax__gte=0, total__gte=0),
                name="quote_totals_not_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "status", "valid_until"], name="quote_status_validity_idx"),
            models.Index(fields=["organization", "quoted_on"], name="quote_day_idx"),
        ]

    def __str__(self) -> str:
        return self.number


class QuoteLine(OrganizationScopedModel):
    """One product of a quote: kg, price per kg and an optional discount in percent.

    The amounts are computed by the services: gross = kg × price (rounded once), discount = gross ×
    rate / 100 (rounded once), amount = gross − discount.
    """

    # A draft's lines are replaced as a whole when it changes; a quote itself is never deleted.
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    quantity = QuantityField()
    # DT per kg: the sale price in force when it was typed, or the one agreed with the customer.
    unit_price = MoneyField()
    # Percent, 2 decimals: 5.00 = 5 %.
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    gross_amount = MoneyField()
    discount_amount = MoneyField(default=Decimal("0.000"))
    amount = MoneyField()

    class Meta:
        ordering = ["quote", "id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="quote_line_quantity_positive"),
            models.CheckConstraint(condition=models.Q(unit_price__gt=0), name="quote_line_price_positive"),
            models.CheckConstraint(
                condition=models.Q(discount_rate__gte=0, discount_rate__lte=100), name="quote_line_discount_percent"
            ),
            models.CheckConstraint(
                condition=models.Q(gross_amount__gte=0, discount_amount__gte=0, amount__gte=0),
                name="quote_line_amounts_not_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quote} · {self.product_id}"
