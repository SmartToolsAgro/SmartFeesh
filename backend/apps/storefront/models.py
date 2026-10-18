from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import OrganizationScopedModel, TimeStampedModel
from apps.core.money import QuantityField


class SiteSettings(OrganizationScopedModel, TimeStampedModel):
    """How a visitor reaches the company, as the public site shows it (D-186), set in the office app.

    One row per organization, made on the first save. An empty field is not shown on the site. The phone is
    stored written one way (`services.normalize_phone`), so the site can make a "call" link of it.
    """

    phone = models.CharField(max_length=30, blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=250, blank=True)
    opening_hours = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name_plural = "site settings"
        constraints = [
            models.UniqueConstraint(fields=["organization"], name="one_site_settings_per_organization"),
        ]

    def __str__(self) -> str:
        return f"Site · {self.organization_id}"


class SiteProduct(OrganizationScopedModel, TimeStampedModel):
    """The office's choices for one product on the public site (D-186).

    Every active product of the application is on the site, with its photo; a row exists only once the office
    changes something for it: hides it (`is_published` off), gives it a web price, a text or a place in the list.
    The web price is the site's alone: it never changes the day's price (`ProductPrice`), the price lists or a
    sale. Empty: the site shows "prix sur demande". An archived product never shows.
    """

    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="+")
    is_published = models.BooleanField(default=True)
    # DT per kg, shown to visitors as an indication; the office confirms the real price on the phone.
    web_price = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    description = models.CharField(max_length=300, blank=True)
    # Shown on the site from the smallest; equal positions follow the product name.
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "product__name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "product"], name="site_product_once_per_organization"),
            models.CheckConstraint(
                condition=models.Q(web_price__isnull=True) | models.Q(web_price__gt=0),
                name="site_product_web_price_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"Site · {self.product_id}"


class WebRequestKind(models.TextChoices):
    # A visitor asks for prices: the office answers with a quote.
    QUOTE = "quote", _("Demande de devis")
    # A visitor wants to buy: the office calls back to confirm the price and the delivery.
    ORDER = "order", _("Commande")


class WebRequestStatus(models.TextChoices):
    NEW = "new", _("Nouvelle")
    HANDLED = "handled", _("Traitée")
    CANCELLED = "cancelled", _("Annulée")


class WebRequest(OrganizationScopedModel, TimeStampedModel):
    """A quote request or an order sent from the public site (D-186).

    Nobody is logged in: the phone number is the only sure way back to the visitor, so it is required. Nothing
    here moves stock or money; the office calls back, then makes the quote or the sale as usual.
    """

    kind = models.CharField(max_length=10, choices=WebRequestKind.choices)
    status = models.CharField(max_length=10, choices=WebRequestStatus.choices, default=WebRequestStatus.NEW)
    full_name = models.CharField(max_length=120)
    # Stored as typed after a check, e.g. "+216 98 123 456" (`services.normalize_phone`).
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    company = models.CharField(max_length=150, blank=True)
    city = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=250, blank=True)
    wanted_on = models.DateField(null=True, blank=True)
    message = models.TextField(blank=True, max_length=2000)
    # The office's side: who closed it, when, and what was agreed on the phone.
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    handled_at = models.DateTimeField(null=True, blank=True)
    office_note = models.TextField(blank=True, max_length=2000)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["organization", "status", "-id"])]

    @property
    def number(self) -> str:
        return f"W-{self.pk:05d}"

    def __str__(self) -> str:
        return f"{self.number} · {self.full_name}"


class WebRequestLine(OrganizationScopedModel):
    request = models.ForeignKey(WebRequest, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    # In the product's base unit (kg).
    quantity = QuantityField()
    # The web price shown to the visitor when they sent it (ARCHITECTURE §4.4); empty: "prix sur demande".
    web_price = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="web_request_line_quantity_positive"),
        ]
