"""Reusable read queries of the public site and of its requests (D-184)."""

from typing import TYPE_CHECKING

from django.conf import settings
from django.db.models import Q, QuerySet

from apps.catalog import selectors as catalog
from apps.core.models import Organization

from .models import SiteProduct, WebRequest, WebRequestStatus

if TYPE_CHECKING:
    from apps.catalog.models import Category


def site_organization() -> Organization | None:
    """The company the public site sells for: `PUBLIC_SITE_ORGANIZATION_ID`, or the oldest active one (one
    company exists today, D-004). None when there is none: the site then shows no catalogue and takes nothing."""
    organizations = Organization.objects.filter(is_active=True)
    chosen = settings.PUBLIC_SITE_ORGANIZATION_ID
    if chosen:
        return organizations.filter(pk=chosen).first()
    return organizations.order_by("id").first()


def site_products_of(organization: Organization) -> QuerySet[SiteProduct]:
    """Every product the office put on the site, shown or hidden, in the site's order (office screen)."""
    return (
        SiteProduct.objects.for_organization(organization)
        .select_related("product__category", "product__base_unit")
        .order_by("position", "product__name", "id")
    )


def site_product_of(organization: Organization, site_product_id: int) -> SiteProduct:
    return site_products_of(organization).get(pk=site_product_id)


def site_products(organization: Organization) -> QuerySet[SiteProduct]:
    """What a visitor sees and may ask for: the published rows of active products. The web price only, never the
    day's price, a cost or the stock (D-184)."""
    return site_products_of(organization).filter(is_published=True, product__is_active=True)


def site_categories(organization: Organization) -> QuerySet["Category"]:
    """The categories of the products shown on the site."""
    shown = site_products(organization).values("product__category_id")
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
