"""Demo public site (D-186): every active product is shown, at today's price rounded up to the half dinar."""

from decimal import ROUND_CEILING, Decimal

from apps.catalog import selectors as catalog
from apps.core.models import Organization, User
from apps.storefront import selectors, services

HALF_DINAR = Decimal("0.5")


def seed_site(*, organization: Organization, actor: User) -> int:
    """Put the products not yet on the site there. Returns how many were added."""
    shown = set(selectors.site_products_of(organization).values_list("product_id", flat=True))
    added = 0
    for product in catalog.products_of(organization):
        if product.pk in shown:
            continue
        price = catalog.current_price_of(product)
        web_price = (price / HALF_DINAR).to_integral_value(ROUND_CEILING) * HALF_DINAR if price else None
        services.add_site_product(organization=organization, actor=actor, product_id=product.pk, web_price=web_price)
        added += 1
    return added
