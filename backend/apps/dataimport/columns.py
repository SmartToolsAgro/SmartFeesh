"""The Excel templates of the data import (P4-T01, D-112): one sheet per kind of data, one column per field.

The first row of the sheet holds the French column titles (a star marks a required one). A second sheet,
"Aide", explains each column. Titles are matched without case, accents' case or the star, so a template
typed by hand still reads.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    key: str
    title: str
    # text | decimal | integer | date
    kind: str = "text"
    required: bool = False
    help: str = ""
    example: str = ""


@dataclass(frozen=True)
class ImportKind:
    key: str
    title: str
    columns: tuple[Column, ...]


CUSTOMER_KINDS = (
    ("restaurant", "Restaurant"),
    ("hotel", "Hôtel"),
    ("fish_shop", "Poissonnerie"),
    ("supermarket", "Supermarché"),
    ("wholesaler", "Grossiste"),
    ("caterer", "Traiteur"),
    ("individual", "Particulier"),
)

REFERENCE_HELP = "Laissez vide pour que le système en donne une. Une référence déjà connue est ignorée."

PRODUCTS = ImportKind(
    "products",
    "Produits",
    (
        Column("reference", "Référence", help=REFERENCE_HELP, example="CR-001"),
        Column("name", "Nom", required=True, example="Crevette Royale"),
        Column("name_ar", "Nom en arabe"),
        Column(
            "category", "Catégorie", required=True, help="Le nom d'une catégorie qui existe déjà.", example="Crustacés"
        ),
        Column("sale_price", "Prix de vente (DT/kg)", "decimal", True, "Prix du jour au départ, en dinars.", "42,000"),
        Column("min_stock", "Stock minimum (kg)", "decimal", help="Alerte quand le stock passe dessous."),
        Column("vat_rate", "TVA (%)", "decimal", help="Vide : le taux de la société. 0 : exonéré."),
        Column("storage_temp_min", "Température min (°C)", "decimal"),
        Column("storage_temp_max", "Température max (°C)", "decimal"),
    ),
)

SUPPLIERS = ImportKind(
    "suppliers",
    "Fournisseurs",
    (
        Column("reference", "Référence", help=REFERENCE_HELP, example="F-001"),
        Column("name", "Nom", required=True, example="Pêcherie du Golfe"),
        Column("tax_id", "Matricule fiscal", help="Par exemple 1234567A/A/M/000.", example="1234567A/A/M/000"),
        Column("phone", "Téléphone"),
        Column("email", "E-mail"),
        Column("address", "Adresse"),
        Column("city", "Ville", example="Sfax"),
        Column("notes", "Remarques"),
    ),
)

CUSTOMERS = ImportKind(
    "customers",
    "Clients",
    (
        Column("reference", "Référence", help=REFERENCE_HELP, example="C-001"),
        Column("name", "Nom", required=True, example="Restaurant Le Corail"),
        Column(
            "kind",
            "Type",
            required=True,
            help="Un de : " + ", ".join(label for _code, label in CUSTOMER_KINDS) + ".",
            example="Restaurant",
        ),
        Column("tax_id", "Matricule fiscal"),
        Column("phone", "Téléphone"),
        Column("email", "E-mail"),
        Column("address", "Adresse"),
        Column("city", "Ville", example="Sfax"),
        Column(
            "credit_limit", "Limite de crédit (DT)", "decimal", help="0 ou vide : pas de crédit.", example="500,000"
        ),
        Column("payment_terms_days", "Délai de paiement (jours)", "integer", example="30"),
        Column("notes", "Remarques"),
    ),
)

EMPLOYEES = ImportKind(
    "employees",
    "Employés",
    (
        Column("reference", "Référence", help=REFERENCE_HELP, example="E-001"),
        Column("name", "Nom", required=True, example="Ali Ben Salah"),
        Column("position", "Poste", example="Manutentionnaire"),
        Column("phone", "Téléphone"),
        Column("hire_date", "Date d'embauche", "date", help="JJ/MM/AAAA.", example="01/03/2024"),
        Column("monthly_salary", "Salaire mensuel (DT)", "decimal", example="1200,000"),
        Column("cnss_number", "Numéro CNSS"),
        Column("cnss_rate", "Taux CNSS patronal (%)", "decimal", help="Vide : 17,07 %."),
        Column(
            "employee_cnss_rate",
            "Taux CNSS salarié (%)",
            "decimal",
            help="Retenu sur le salaire brut. Vide : 9,18 % (provisoire).",
        ),
        Column("notes", "Remarques"),
    ),
)

OPENING_STOCK = ImportKind(
    "opening_stock",
    "Stock d'ouverture",
    (
        Column(
            "product", "Produit (référence)", required=True, help="La référence d'un produit connu.", example="CR-001"
        ),
        Column(
            "location",
            "Emplacement",
            required=True,
            help="Le nom exact d'une chambre froide ou d'un camion.",
            example="Chambre froide 1",
        ),
        Column(
            "supplier",
            "Fournisseur (référence)",
            required=True,
            help="Le fournisseur du lot, par sa référence.",
            example="F-001",
        ),
        Column("quantity", "Quantité (kg)", "decimal", True, "Le poids en stock au jour de l'ouverture.", "120,500"),
        Column("unit_cost", "Coût d'achat (DT/kg)", "decimal", True, "Prix d'achat du lot, sans TVA.", "21,000"),
        Column("received_on", "Date de réception", "date", True, "Jour d'arrivée du lot (JJ/MM/AAAA).", "05/10/2026"),
        Column("use_by", "Date limite", "date", help="JJ/MM/AAAA."),
    ),
)

CUSTOMER_DEBTS = ImportKind(
    "customer_debts",
    "Dettes clients",
    (
        Column(
            "customer", "Client (référence)", required=True, help="La référence d'un client connu.", example="C-001"
        ),
        Column("amount", "Montant dû (DT)", "decimal", True, "Ce que le client doit encore à l'ouverture.", "1250,000"),
        Column(
            "owed_on",
            "Dû depuis le",
            "date",
            True,
            "Date de la dette : l'ancienneté en part (JJ/MM/AAAA).",
            "15/09/2026",
        ),
        Column("notes", "Remarques", help="Par exemple le numéro de la facture papier."),
    ),
)

SUPPLIER_DEBTS = ImportKind(
    "supplier_debts",
    "Dettes fournisseurs",
    (
        Column(
            "supplier",
            "Fournisseur (référence)",
            required=True,
            help="La référence d'un fournisseur connu.",
            example="F-001",
        ),
        Column("amount", "Montant dû (DT)", "decimal", True, "Ce que vous lui devez encore à l'ouverture.", "3400,000"),
        Column("invoice_date", "Date de la facture", "date", True, "JJ/MM/AAAA.", "20/09/2026"),
        Column("due_date", "Échéance", "date", help="Vide : le jour de la facture."),
        Column("supplier_reference", "N° de facture du fournisseur"),
        Column("notes", "Remarques"),
    ),
)

KINDS: dict[str, ImportKind] = {
    kind.key: kind
    for kind in (PRODUCTS, SUPPLIERS, CUSTOMERS, EMPLOYEES, OPENING_STOCK, CUSTOMER_DEBTS, SUPPLIER_DEBTS)
}
