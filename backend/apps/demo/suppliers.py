"""Demo suppliers: the stand-ins of docs/spec/sample/suppliers.csv, until the client's real list arrives.

Their agreements (profit sharing, investment) come with Phase 6; only the notes mention them for now.
"""

from apps.core.models import Organization, User
from apps.partners import selectors, services
from apps.partners.services import ContactFields

# reference, name, tax ID, phone, city, notes, contacts (invented, like everything in the sample)
SUPPLIERS: list[tuple[str, str, str, str, str, str, list[ContactFields]]] = [
    (
        "F-001",
        "Pêcherie Kerkennah",
        "0000001A/A/M/000",
        "+216 74 000 101",
        "Kerkennah (Sfax)",
        "Pêcheur / armateur. Partenaire : part sur le bénéfice net de ses propres produits.",
        [{"name": "Hédi Ben Salah", "role": "Armateur", "phone": "+216 98 000 101"}],
    ),
    (
        "F-002",
        "Mareyeur Port de Sfax",
        "0000002B/A/M/000",
        "+216 74 000 102",
        "Sfax",
        "Mareyeur. Fournisseur classique payé sur facture.",
        [
            {"name": "Karim Trabelsi", "role": "Gérant", "phone": "+216 98 000 102"},
            {"name": "Amel Jarraya", "role": "Comptable", "email": "compta@mareyeur-sfax.example"},
        ],
    ),
    (
        "F-003",
        "Aqua Monastir",
        "0000003C/A/M/000",
        "+216 73 000 103",
        "Monastir",
        "Aquaculture : dorade et loup d'élevage.",
        [{"name": "Sonia Mejri", "role": "Commerciale", "phone": "+216 98 000 103"}],
    ),
    (
        "F-004",
        "Surgelés du Sahel",
        "0000004D/A/M/000",
        "+216 73 000 104",
        "Sousse",
        "Importateur / surgelés. Partenaire investisseur : capital remboursé par la part de bénéfice.",
        [{"name": "Walid Gharbi", "role": "Directeur", "phone": "+216 98 000 104"}],
    ),
]


def seed_suppliers(*, organization: Organization, actor: User | None) -> int:
    """Create the demo suppliers that do not exist yet. Returns how many were created."""
    existing = {
        reference.lower()
        for reference in selectors.suppliers_of(organization, status="all").values_list("reference", flat=True)
    }
    created = 0
    for reference, name, tax_id, phone, city, notes, contacts in SUPPLIERS:
        if reference.lower() in existing:
            continue
        services.create_supplier(
            organization=organization,
            actor=actor,
            reference=reference,
            name=name,
            tax_id=tax_id,
            phone=phone,
            city=city,
            notes=notes,
            contacts=contacts,
        )
        created += 1
    return created
