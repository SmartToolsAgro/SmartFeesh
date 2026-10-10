"""Demo catalogue: the stand-in products of docs/spec/sample/products.csv, until the client's real list arrives."""

from decimal import Decimal

from apps.catalog import selectors, services
from apps.core.models import Organization, User

FRESH = (Decimal("0"), Decimal("4"))
FROZEN = (None, Decimal("-18"))

# reference, French name, Arabic name, category, storage, sale price (DT/kg), minimum stock (kg), drawing
PRODUCTS = [
    ("CR-001", "Crevette Royale", "قمرون ملكي", "Crustacés", FRESH, "42.000", "20", "shrimp"),
    ("CD-002", "Crevette décortiquée", "قمرون مقشّر", "Crustacés", FROZEN, "38.000", "15", "peeled"),
    ("DO-003", "Dorade royale", "وراطة", "Poissons", FRESH, "24.500", "25", "fish"),
    ("LO-004", "Loup de mer", "قاروص", "Poissons", FRESH, "27.000", "20", "bass"),
    ("CA-005", "Calamar", "كلمار", "Céphalopodes", FROZEN, "29.000", "12", "squid"),
    ("PO-006", "Poulpe", "قرنيط", "Céphalopodes", FRESH, "31.500", "10", "octopus"),
    ("MO-007", "Moules", "بلح البحر", "Coquillages", FRESH, "9.500", "15", "mussel"),
    ("SY-008", "Symphonie Marine", "سمفونية البحر", "Mélanges", FROZEN, "33.000", "8", "mix"),
    ("RO-009", "Rouget", "تريليا", "Poissons", FRESH, "14.000", "15", "fish"),
    ("SA-010", "Sardine", "سردينة", "Poissons", FRESH, "7.500", "30", "fish"),
    ("MU-011", "Mulet", "بوري", "Poissons", FRESH, "13.500", "15", "fish"),
    ("SE-012", "Seiche", "شوابي", "Céphalopodes", FRESH, "26.000", "10", "squid"),
]


def seed_catalogue(*, organization: Organization, actor: User | None) -> int:
    """Create the demo categories and products that do not exist yet. Returns how many products were created."""
    categories = {category.name: category for category in selectors.categories_of(organization)}
    existing = {
        reference.lower()
        for reference in selectors.products_of(organization, status="all").values_list("reference", flat=True)
    }
    created = 0
    for reference, name, name_ar, category_name, (low, high), price, min_stock, drawing in PRODUCTS:
        if category_name not in categories:
            categories[category_name] = services.create_category(
                organization=organization, actor=actor, name=category_name
            )
        if reference.lower() in existing:
            continue
        services.create_product(
            organization=organization,
            actor=actor,
            reference=reference,
            name=name,
            name_ar=name_ar,
            category=categories[category_name],
            min_stock=min_stock,
            storage_temp_min=low,
            storage_temp_max=high,
            illustration=drawing,
            sale_price=price,
        )
        created += 1
    return created
