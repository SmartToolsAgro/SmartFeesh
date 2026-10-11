"""Demo quotes, like the prototype's "Devis en cours": one sent to Restaurant Le Corail (its 5 kg of Crevette
Royale at 42.000 start the Phase 2 acceptance test), one sent to Hôtel Thyna, one accepted, one refused and
one draft.

Each quote has a fixed `client_uuid`, so running the seed again creates nothing. They are dated on the day of
the first seed; later runs leave them on that day, so the sent ones expire after their validity date as real
ones would.
"""

import datetime as dt
import uuid

from django.utils import timezone

from apps.catalog import selectors as catalog
from apps.core.models import Organization, User
from apps.partners import selectors as partners
from apps.sales import selectors, services

SEED_NAMESPACE = uuid.UUID("0b5d7c2e-61a4-4f3b-8e0d-93c2a7f15e64")
FRESH_ROOM = "Chambre froide 1 (frais)"
# key, customer reference, what happens to it, validity in days, notes,
# lines: product reference, kg, price per kg (None: the price in force), discount % (None: none)
QUOTES: list[tuple[str, str, str, int, str, list[tuple[str, str, str | None, str | None]]]] = [
    (
        "corail",
        "C-001",
        "sent",
        3,
        "",
        [("CR-001", "5", None, None), ("CA-005", "3", None, None), ("SY-008", "2.5", None, None)],
    ),
    (
        "thyna",
        "C-002",
        "sent",
        7,
        "Livraison pour le week-end du séminaire.",
        [("LO-004", "20", "26.000", None), ("DO-003", "25", None, "5"), ("PO-006", "15", None, None)],
    ),
    ("sidi-mansour", "C-004", "accepted", 3, "", [("CR-001", "4", None, None), ("SE-012", "4", None, None)]),
    ("el-bahr", "C-003", "refused", 3, "", [("SA-010", "60", None, None), ("MU-011", "40", None, "3")]),
    ("ennour", "C-005", "draft", 5, "", [("MO-007", "30", None, None), ("RO-009", "12", None, None)]),
]


def seed_quotes(*, organization: Organization, actor: User | None) -> int:
    """Create the demo quotes that do not exist yet. Returns how many were created."""
    customers = {customer.reference: customer for customer in partners.customers_of(organization, status="all")}
    products = {product.reference: product for product in catalog.products_of(organization, status="all")}
    existing = set(selectors.quotes_of(organization).exclude(client_uuid=None).values_list("client_uuid", flat=True))
    today = timezone.localdate()
    created = 0
    for key, customer, outcome, validity_days, notes, lines in QUOTES:
        client_uuid = uuid.uuid5(SEED_NAMESPACE, key)
        if client_uuid in existing:
            continue
        quote = services.create_quote(
            organization=organization,
            actor=actor,
            customer=customers[customer],
            quoted_on=today,
            valid_until=today + dt.timedelta(days=validity_days),
            notes=notes,
            lines=[
                {"product": products[reference], "quantity": kg, "unit_price": price, "discount_rate": discount}
                for reference, kg, price, discount in lines
            ],
            client_uuid=client_uuid,
            send=outcome != "draft",
        )
        if outcome == "accepted":
            services.accept_quote(quote=quote, actor=actor)
        elif outcome == "refused":
            services.refuse_quote(quote=quote, actor=actor, reason="Prix trop élevé cette semaine.")
        created += 1
    return created
