"""Demo prices: a minimum price per product (80 % of today's price) and one customer price list."""

from decimal import Decimal

from apps.catalog import selectors, services
from apps.core.models import Organization, User
from apps.core.money import money
from apps.partners import selectors as partner_selectors

HOTEL_REFERENCE = "C-002"
HOTEL_LIST = "Hôtel Thyna"
# product reference, special price (DT/kg)
HOTEL_PRICES = [("CR-001", "39.500"), ("DO-003", "22.500"), ("LO-004", "25.000")]


def seed_prices(*, organization: Organization, actor: User | None) -> int:
    """Set the minimum prices that are missing and create the hotel price list. Returns how many were created."""
    created = 0
    products = list(selectors.products_of(organization))
    changes: list[services.PriceChange] = [
        {"product": product, "min_price": money(price * Decimal("0.8"))}
        for product in products
        if product.min_price is None and (price := selectors.current_price_of(product)) is not None
    ]
    if changes:
        services.set_sale_prices(organization=organization, actor=actor, changes=changes)
        created += len(changes)
    hotel = partner_selectors.customers_of(organization, status="all").filter(reference=HOTEL_REFERENCE).first()
    if hotel is not None and not selectors.price_lists_of(organization, customer_id=hotel.pk, status="all").exists():
        by_reference = {product.reference: product for product in products}
        items: list[services.PriceListItemInput] = [
            {"product": by_reference[reference], "price": price}
            for reference, price in HOTEL_PRICES
            if reference in by_reference
        ]
        services.create_price_list(
            organization=organization, actor=actor, name=HOTEL_LIST, customer_id=hotel.pk, items=items
        )
        created += 1
    return created
