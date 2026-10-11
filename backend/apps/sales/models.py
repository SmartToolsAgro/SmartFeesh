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


# ---- Sales (P2-T04, D-051) ----


class SaleStatus(models.TextChoices):
    # Being typed: customer, place, lines and prices may still change; no stock has moved.
    DRAFT = "draft", _("Brouillon")
    # The goods left the stock (oldest batch first) and the customer owes the amount not paid.
    CONFIRMED = "confirmed", _("Confirmée")
    # Given up: a draft simply stops; a confirmed sale brings its kilos back to the same batches.
    CANCELLED = "cancelled", _("Annulée")


class SalePaymentMethod(models.TextChoices):
    """How the customer paid at the sale. Full customer payments are P2-T06's `CustomerPayment`."""

    CASH = "cash", _("Espèces")
    CHEQUE = "cheque", _("Chèque")
    TRANSFER = "transfer", _("Virement")
    CARD = "card", _("Carte bancaire")


class PriceSource(models.TextChoices):
    """Where the price of a sale line came from."""

    # The customer's own price list (D-049).
    PRICE_LIST = "price_list", _("Liste du client")
    # The daily price in force at the sale's moment (D-030).
    DAILY = "daily", _("Prix du jour")
    # The accepted quote's line (D-050).
    QUOTE = "quote", _("Devis")
    # Typed by the seller.
    TYPED = "typed", _("Saisi")


class Sale(OrganizationScopedModel, TimeStampedModel):
    """Goods sold to a customer from one place (a cold room's counter or a truck), at one moment.

    A draft moves nothing. Confirming it takes each line's kilos out of the place oldest batch first
    (`inventory.services.post_fifo_movements`) and keeps, per line, which batches went at what cost
    (`SaleLineBatch`), so a lot's sales and profit are known later (D-040). A confirmed sale never changes:
    cancelling it brings the same kilos back to the same batches by `customer_return` movements, and the
    sale stays, marked cancelled. Never deleted.
    """

    # "VE-0001", "VE-0002"... per organization, given when the draft is created.
    number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=SaleStatus.choices, default=SaleStatus.DRAFT)
    # The walk-in customer ("Client de passage") for counter sales without a name (D-047).
    customer = models.ForeignKey("partners.Customer", on_delete=models.PROTECT, related_name="sales")
    # Where the goods leave from: a cold room open to counter sales, or a truck.
    location = models.ForeignKey("inventory.StockLocation", on_delete=models.PROTECT, related_name="+")
    # When the sale was made: its prices are the ones in force then, and its movements happen then.
    sold_at = models.DateTimeField()
    # The accepted quote it came from, if any. One live (not cancelled) sale per quote.
    quote = models.ForeignKey(Quote, null=True, blank=True, on_delete=models.PROTECT, related_name="sales")
    notes = models.TextField(blank=True)
    # Totals computed by the services from the lines, as on quotes.
    subtotal = MoneyField(default=Decimal("0.000"))
    discount_total = MoneyField(default=Decimal("0.000"))
    total_excl_tax = MoneyField(default=Decimal("0.000"))
    # VAT hook (P2-T05): empty until the finance settings exist; `total` is the amount without VAT.
    tax_amount = models.DecimalField[Decimal | None, Decimal | None](
        max_digits=14, decimal_places=3, null=True, blank=True
    )
    total = MoneyField(default=Decimal("0.000"))
    # Cost of the goods sold (FIFO batches × their cost per kg), known once confirmed.
    cost_total = models.DecimalField[Decimal | None, Decimal | None](
        max_digits=14, decimal_places=3, null=True, blank=True
    )
    # Paid on the spot (cash at the counter, a cheque handed to the driver...). P2-T06 brings full customer
    # payments; until then the receivable of a confirmed sale is `amount_due`.
    amount_paid = MoneyField(default=Decimal("0.000"))
    payment_method = models.CharField(max_length=20, choices=SalePaymentMethod.choices, blank=True)
    # Cheque number, transfer reference...
    payment_reference = models.CharField(max_length=50, blank=True)
    # total − amount_paid: what the customer still owes for this sale (P2-T06 hook).
    amount_due = MoneyField(default=Decimal("0.000"))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True)
    # Sent by an app that may retry (the driver app, the seed): the same request never makes two sales.
    client_uuid = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-sold_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "number"], name="sale_number_unique_per_organization"),
            models.UniqueConstraint(
                fields=["organization", "client_uuid"],
                condition=models.Q(client_uuid__isnull=False),
                name="sale_client_uuid_unique_per_organization",
            ),
            # A quote becomes one sale; once that sale is cancelled it may become another.
            models.UniqueConstraint(
                fields=["quote"],
                condition=models.Q(quote__isnull=False) & ~models.Q(status="cancelled"),
                name="one_live_sale_per_quote",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    subtotal__gte=0,
                    discount_total__gte=0,
                    total_excl_tax__gte=0,
                    total__gte=0,
                    amount_paid__gte=0,
                    amount_due__gte=0,
                ),
                name="sale_amounts_not_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "status", "sold_at"], name="sale_status_day_idx"),
            models.Index(fields=["organization", "customer", "sold_at"], name="sale_customer_idx"),
            models.Index(fields=["organization", "location", "sold_at"], name="sale_location_idx"),
        ]

    def __str__(self) -> str:
        return self.number


class SaleLine(OrganizationScopedModel):
    """One product of a sale: kg, the price per kg actually charged and an optional discount in percent.

    The price is kept here, so later price changes never touch the sale (D-020). Amounts as on quotes.
    Once confirmed, `batches` says which lots the kilos came from and at what cost.
    """

    # A draft's lines are replaced as a whole when it changes; a sale itself is never deleted.
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    quantity = QuantityField()
    unit_price = MoneyField()
    price_source = models.CharField(max_length=20, choices=PriceSource.choices)
    # The price was below the product's minimum when typed: a warning, never a block (D-049).
    below_minimum = models.BooleanField(default=False)
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    gross_amount = MoneyField()
    discount_amount = MoneyField(default=Decimal("0.000"))
    # gross − discount, without VAT: the line's revenue.
    amount = MoneyField()
    # Cost of the goods of this line (sum of its batches), known once confirmed.
    cost_amount = models.DecimalField[Decimal | None, Decimal | None](
        max_digits=14, decimal_places=3, null=True, blank=True
    )

    class Meta:
        ordering = ["sale", "id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="sale_line_quantity_positive"),
            models.CheckConstraint(condition=models.Q(unit_price__gt=0), name="sale_line_price_positive"),
            models.CheckConstraint(
                condition=models.Q(discount_rate__gte=0, discount_rate__lte=100), name="sale_line_discount_percent"
            ),
            models.CheckConstraint(
                condition=models.Q(gross_amount__gte=0, discount_amount__gte=0, amount__gte=0),
                name="sale_line_amounts_not_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.sale} · {self.product_id}"


class SaleLineBatch(OrganizationScopedModel):
    """The kilos of one sale line taken from one batch (lot) when the sale was confirmed, oldest batch
    first: the batch, its cost per kg then (snapshot), the cost and the line's revenue shared by kg.

    What a lot sold, for how much and at what cost is read from these rows (`selectors.batch_sales`), the
    base of its result (D-040). Written once at confirmation and never changed; a cancelled sale keeps them
    and its status says they no longer count.
    """

    line = models.ForeignKey(SaleLine, on_delete=models.PROTECT, related_name="batches")
    batch = models.ForeignKey("inventory.Batch", on_delete=models.PROTECT, related_name="+")
    quantity = QuantityField()
    # The batch's cost per kg when sold.
    unit_cost = MoneyField()
    # quantity × unit_cost, rounded once.
    cost_amount = MoneyField()
    # The line's amount (without VAT) shared by kg over its batches; the last batch takes the rounding rest,
    # so the parts always add up to the line.
    revenue_amount = MoneyField()

    class Meta:
        ordering = ["line", "id"]
        constraints = [
            models.UniqueConstraint(fields=["line", "batch"], name="one_row_per_sale_line_and_batch"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="sale_line_batch_quantity_positive"),
        ]
        indexes = [models.Index(fields=["organization", "batch"], name="sale_line_batch_lot_idx")]

    def __str__(self) -> str:
        return f"{self.line} · {self.batch_id} · {self.quantity} kg"
