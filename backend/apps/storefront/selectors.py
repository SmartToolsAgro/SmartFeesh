"""Reusable read queries of the public site and of its requests (D-186)."""

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from django.conf import settings
from django.db.models import Q, QuerySet

from apps.catalog import selectors as catalog
from apps.core.models import Organization

from .models import SiteProduct, SiteSettings, WebRequest, WebRequestStatus

if TYPE_CHECKING:
    from apps.catalog.models import Category, Product


def site_organization() -> Organization | None:
    """The company the public site sells for: `PUBLIC_SITE_ORGANIZATION_ID`, or the oldest active one (one
    company exists today, D-004). None when there is none: the site then shows no catalogue and takes nothing."""
    organizations = Organization.objects.filter(is_active=True)
    chosen = settings.PUBLIC_SITE_ORGANIZATION_ID
    if chosen:
        return organizations.filter(pk=chosen).first()
    return organizations.order_by("id").first()


# Products the office never placed come after the ones it did, by name.
UNORDERED = 1_000_000


@dataclass(frozen=True)
class SiteOffer:
    """One product as the public site deals with it: the catalogue's product (with `current_price`, the day's price,
    for the office only) and the office's settings for it, when it changed any."""

    product: "Product"
    settings: SiteProduct | None

    @property
    def product_id(self) -> int:
        return self.product.pk

    @property
    def is_published(self) -> bool:
        return self.settings is None or self.settings.is_published

    @property
    def web_price(self) -> Decimal | None:
        return self.settings.web_price if self.settings else None

    @property
    def description(self) -> str:
        return self.settings.description if self.settings else ""

    @property
    def position(self) -> int:
        return self.settings.position if self.settings else UNORDERED

    @property
    def day_price(self) -> Decimal | None:
        return catalog.current_price_of(self.product)


def site_offers(organization: Organization, *, include_hidden: bool = False) -> list[SiteOffer]:
    """Every active product of the company with the office's site settings, in the site's order. Without
    `include_hidden`, only what visitors see."""
    rows = {row.product_id: row for row in SiteProduct.objects.for_organization(organization)}
    offers = [SiteOffer(product, rows.get(product.pk)) for product in catalog.products_of(organization)]
    if not include_hidden:
        offers = [offer for offer in offers if offer.is_published]
    return sorted(offers, key=lambda offer: (offer.position, offer.product.name.lower(), offer.product_id))


def site_offer_of(organization: Organization, product_id: int) -> SiteOffer:
    """One product of the company and its site settings. Raises ObjectDoesNotExist outside the organization."""
    product = catalog.product_of(organization, product_id)
    return SiteOffer(product, SiteProduct.objects.for_organization(organization).filter(product=product).first())


def site_products(organization: Organization) -> list[SiteOffer]:
    """What a visitor sees and may ask for: the active products the office did not hide. The web price only,
    never the day's price, a cost or the stock (D-186)."""
    return site_offers(organization)


def site_categories(organization: Organization) -> QuerySet["Category"]:
    """The categories of the products shown on the site."""
    shown = {offer.product.category_id for offer in site_products(organization)}
    return catalog.categories_of(organization).filter(pk__in=shown)


def web_requests_of(
    organization: Organization, *, status: str | None = None, kind: str | None = None, search: str = ""
) -> QuerySet[WebRequest]:
    """The site's requests, newest first, with their lines."""
    requests = (
        WebRequest.objects.for_organization(organization)
        .select_related("handled_by")
        .prefetch_related("lines__product__base_unit")
        .order_by("-id")
    )
    if status:
        requests = requests.filter(status=status)
    if kind:
        requests = requests.filter(kind=kind)
    if search := search.strip():
        found = Q(full_name__icontains=search) | Q(phone__icontains=search) | Q(company__icontains=search)
        digits = search.upper().removeprefix("W-").lstrip("0")
        if digits.isdigit():
            found |= Q(pk=int(digits))
        requests = requests.filter(found)
    return requests


def web_request_of(organization: Organization, request_id: int) -> WebRequest:
    return web_requests_of(organization).get(pk=request_id)


def new_count(organization: Organization) -> int:
    return WebRequest.objects.for_organization(organization).filter(status=WebRequestStatus.NEW).count()


def site_settings_of(organization: Organization) -> SiteSettings:
    """The site's contact details; an unsaved empty row until the office saves them once."""
    found = SiteSettings.objects.for_organization(organization).first()
    return found if found is not None else SiteSettings(organization=organization)
