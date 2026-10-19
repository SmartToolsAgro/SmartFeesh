"""Demo public site (D-186): every active product is on the site; those with a day's price get a web price, the day's
price rounded up to the half dinar. Run again, it changes nothing."""

from decimal import ROUND_CEILING, Decimal

from apps.core.models import Organization, User
from apps.storefront import selectors, services

HALF_DINAR = Decimal("0.5")


def seed_site(*, organization: Organization, actor: User) -> int:
    """Give a web price to the products the office never set up on the site. Returns how many were set."""
    priced = 0
    for offer in selectors.site_offers(organization, include_hidden=True):
        if offer.settings is not None or offer.day_price is None:
            continue
        web_price = (offer.day_price / HALF_DINAR).to_integral_value(ROUND_CEILING) * HALF_DINAR
        services.update_site_product(
            organization=organization, actor=actor, product_id=offer.product_id, changes={"web_price": web_price}
        )
        priced += 1
    return priced
