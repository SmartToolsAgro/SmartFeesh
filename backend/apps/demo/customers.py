"""Demo customers: the stand-ins of docs/spec/sample/customers.csv, until the client's real list arrives.

The opening balances of that file come with receivables (P2-T06); only the credit limit and the payment
terms are loaded here. The walk-in customer is created last, so it gets C-009 as in the sample.
"""

from decimal import Decimal

from apps.core.models import Organization, User
from apps.partners import selectors, services
from apps.partners.services import ContactFields

# reference, name, kind, tax ID, phone, city, credit limit (DT), payment terms (days), contacts (invented)
CUSTOMERS: list[tuple[str, str, str, str, str, str, str, int, list[ContactFields]]] = [
    (
        "C-001",
        "Restaurant Le Corail",
        "restaurant",
        "0000101A/A/M/000",
        "+216 74 000 201",
        "Sfax centre",
        "2000.000",
        30,
        [{"name": "Chef Moncef Gargouri", "role": "Chef", "phone": "+216 98 000 201"}],
    ),
    (
        "C-002",
        "Hôtel Thyna",
        "hotel",
        "0000102B/A/M/000",
        "+216 74 000 202",
        "Thyna",
        "5000.000",
        45,
        [
            {"name": "Sonia Kammoun", "role": "Économat", "phone": "+216 98 000 202"},
            {"name": "Direction financière", "role": "Comptabilité", "email": "compta@hotel-thyna.example"},
        ],
    ),
    (
        "C-003",
        "Poissonnerie El Bahr",
        "fish_shop",
        "0000103C/A/M/000",
        "+216 74 000 203",
        "Sakiet Ezzit",
        "1500.000",
        15,
        [],
    ),
    (
        "C-004",
        "Café-Resto Sidi Mansour",
        "restaurant",
        "0000104D/A/M/000",
        "+216 74 000 204",
        "Sidi Mansour",
        "800.000",
        15,
        [],
    ),
    (
        "C-005",
        "Supermarché Ennour",
        "supermarket",
        "0000105E/A/M/000",
        "+216 74 000 205",
        "Route Gremda",
        "6000.000",
        60,
        [{"name": "Rachid Mnif", "role": "Acheteur rayon marée", "phone": "+216 98 000 205"}],
    ),
    (
        "C-006",
        "Restaurant Dar El Hout",
        "restaurant",
        "0000106F/A/M/000",
        "+216 74 000 206",
        "Sakiet Eddaier",
        "1500.000",
        30,
        [],
    ),
    (
        "C-007",
        "Marée du Sud",
        "wholesaler",
        "0000107G/A/M/000",
        "+216 74 000 207",
        "Mahrès",
        "8000.000",
        30,
        [{"name": "Lotfi Hamdi", "role": "Gérant", "phone": "+216 98 000 207"}],
    ),
    (
        "C-008",
        "Traiteur Les Saveurs",
        "caterer",
        "0000108H/A/M/000",
        "+216 74 000 208",
        "Route de Tunis",
        "1000.000",
        15,
        [],
    ),
]


def seed_customers(*, organization: Organization, actor: User | None) -> int:
    """Create the demo customers that do not exist yet, then the walk-in one. Returns how many were created."""
    existing = {
        reference.lower()
        for reference in selectors.customers_of(organization, status="all").values_list("reference", flat=True)
    }
    created = 0
    for reference, name, kind, tax_id, phone, city, credit_limit, payment_terms_days, contacts in CUSTOMERS:
        if reference.lower() in existing:
            continue
        services.create_customer(
            organization=organization,
            actor=actor,
            reference=reference,
            name=name,
            kind=kind,
            tax_id=tax_id,
            phone=phone,
            city=city,
            credit_limit=Decimal(credit_limit),
            payment_terms_days=payment_terms_days,
            contacts=contacts,
        )
        created += 1
    if not selectors.customers_of(organization, status="all").filter(is_walk_in=True).exists():
        services.ensure_walk_in_customer(organization=organization, actor=actor)
        created += 1
    return created
