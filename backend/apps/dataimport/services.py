"""Loading the client's data from Excel (P4-T01, D-112).

An import reads a filled template and creates the rows through the same services as the screens
(`create_product`, `create_supplier`...), so every rule of the screens applies and every row is audited.
The same code serves the **dry run** (nothing is kept: the transaction is rolled back at the end, the report
is the same) and the **real import**, which is all or nothing: a single error anywhere writes nothing.
A row whose reference already exists is skipped, not an error, so a file may be sent again.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.catalog import selectors as catalog_selectors
from apps.catalog import services as catalog
from apps.core.models import Organization, User
from apps.hr import selectors as hr_selectors
from apps.hr import services as hr
from apps.inventory import selectors as inventory_selectors
from apps.inventory import services as inventory
from apps.partners import selectors as partners_selectors
from apps.partners import services as partners
from apps.purchasing import selectors as purchasing_selectors
from apps.purchasing import services as purchasing
from apps.sales import selectors as sales_selectors
from apps.sales import services as sales

from . import workbook
from .columns import CUSTOMER_KINDS, KINDS, Column, ImportKind
from .workbook import SheetRow, WorkbookError

__all__ = ["ColumnError", "ImportReport", "RowReport", "WorkbookError", "run_import", "template_for"]

CREATED = "created"
SKIPPED = "skipped"
ERROR = "error"


@dataclass
class ColumnError:
    column: str
    message: str


@dataclass
class RowReport:
    row: int
    status: str
    reference: str = ""
    name: str = ""
    errors: list[ColumnError] = field(default_factory=list)


@dataclass
class ImportReport:
    kind: str
    dry_run: bool
    # True only for a real import without any error: the rows are saved.
    committed: bool = False
    created: int = 0
    skipped: int = 0
    error_count: int = 0
    rows: list[RowReport] = field(default_factory=list)


def template_for(kind_key: str) -> tuple[str, bytes]:
    """The file name and content of the empty template of one kind of data."""
    kind = KINDS[kind_key]
    return f"modele-{kind.key}.xlsx", workbook.template_bytes(kind)


@dataclass
class _Context:
    organization: Organization
    actor: User | None
    # Looked up once per import: products need their category.
    categories: dict[str, Any] = field(default_factory=dict)


Values = dict[str, Any]


def _parse_cells(kind: ImportKind, row: SheetRow) -> tuple[Values, list[ColumnError]]:
    """Typed values from the raw cells; a cell that cannot be read is an error on its column."""
    values: Values = {}
    errors: list[ColumnError] = []
    by_key = {column.key: column for column in kind.columns}
    for key, raw in row.cells.items():
        column: Column = by_key[key]
        try:
            if column.kind == "decimal":
                values[key] = workbook.decimal_value(raw)
            elif column.kind == "integer":
                values[key] = workbook.integer_value(raw)
            elif column.kind == "date":
                values[key] = workbook.date_value(raw)
            else:
                values[key] = workbook.text_value(raw)
        except ValueError as error:
            errors.append(ColumnError(column.title, str(error)))
    for column in kind.columns:
        if column.required and column.key not in row.cells:
            errors.append(ColumnError(column.title, "Obligatoire."))
    return values, errors


def _column_errors(kind: ImportKind, error: ValidationError) -> list[ColumnError]:
    """Errors raised by a service, put on the column of the field they name (else on the first column)."""
    titles = {column.key: column.title for column in kind.columns}
    if hasattr(error, "error_dict"):
        return [
            ColumnError(titles.get(key, kind.columns[0].title), str(message))
            for key, messages in error.message_dict.items()
            for message in messages
        ]
    return [ColumnError(kind.columns[0].title, str(message)) for message in error.messages]


# ---- one creator per kind of data ----


def _exists_product(ctx: _Context, reference: str) -> bool:
    products = catalog_selectors.products_of(ctx.organization, status="all")
    return products.filter(reference__iexact=reference).exists()


def _create_product(ctx: _Context, values: Values) -> None:
    category = ctx.categories.get(values["category"].strip().casefold())
    if category is None:
        known = ", ".join(sorted(item.name for item in ctx.categories.values())) or "aucune"
        raise ValidationError({"category": f"Catégorie inconnue. Catégories existantes : {known}."})
    sale_price = values["sale_price"]
    if sale_price <= 0:
        raise ValidationError({"sale_price": "Le prix doit être supérieur à 0."})
    fields = {key: value for key, value in values.items() if key not in ("category", "sale_price")}
    catalog.create_product(
        organization=ctx.organization, actor=ctx.actor, sale_price=sale_price, category=category, **fields
    )


def _exists_supplier(ctx: _Context, reference: str) -> bool:
    return partners_selectors.suppliers_of(ctx.organization, status="all").filter(reference__iexact=reference).exists()


def _create_supplier(ctx: _Context, values: Values) -> None:
    partners.create_supplier(organization=ctx.organization, actor=ctx.actor, **values)


def _customer_kind(label: str) -> str | None:
    wanted = label.strip().casefold()
    for code, title in CUSTOMER_KINDS:
        if wanted in (code, title.casefold()):
            return code
    return None


def _exists_customer(ctx: _Context, reference: str) -> bool:
    return partners_selectors.customers_of(ctx.organization, status="all").filter(reference__iexact=reference).exists()


def _create_customer(ctx: _Context, values: Values) -> None:
    code = _customer_kind(values["kind"])
    if code is None:
        raise ValidationError({"kind": "Type inconnu. Choisissez : " + ", ".join(t for _c, t in CUSTOMER_KINDS) + "."})
    partners.create_customer(organization=ctx.organization, actor=ctx.actor, **{**values, "kind": code})


def _exists_employee(ctx: _Context, reference: str) -> bool:
    return hr_selectors.employees_of(ctx.organization, status="all").filter(reference__iexact=reference).exists()


def _create_employee(ctx: _Context, values: Values) -> None:
    hr.create_employee(organization=ctx.organization, actor=ctx.actor, **values)


OPENING_REFERENCE = "STOCK-OUVERTURE"


def _opening_batch_match(ctx: _Context, values: Values) -> Any:
    """The product and the supplier of an opening-stock row, or None when one is unknown (create reports it)."""
    product = (
        catalog_selectors.products_of(ctx.organization, status="all")
        .filter(reference__iexact=values.get("product", ""))
        .first()
    )
    supplier = (
        partners_selectors.suppliers_of(ctx.organization, status="all")
        .filter(reference__iexact=values.get("supplier", ""))
        .first()
    )
    return (product, supplier) if product and supplier else None


def _exists_opening(ctx: _Context, values: Values) -> bool:
    """The same opening lot was already imported: sending the file again must not double the stock."""
    found = _opening_batch_match(ctx, values)
    if found is None or "received_on" not in values or "unit_cost" not in values:
        return False
    product, supplier = found
    return (
        inventory_selectors.batches_of(ctx.organization, product_id=product.pk, supplier_id=supplier.pk)
        .filter(receipt_reference=OPENING_REFERENCE, received_on=values["received_on"], unit_cost=values["unit_cost"])
        .exists()
    )


def _create_opening(ctx: _Context, values: Values) -> None:
    found = _opening_batch_match(ctx, values)
    errors: dict[str, str] = {}
    if found is None:
        if (
            not catalog_selectors.products_of(ctx.organization, status="all")
            .filter(reference__iexact=values["product"])
            .exists()
        ):
            errors["product"] = "Produit inconnu."
        if (
            not partners_selectors.suppliers_of(ctx.organization, status="all")
            .filter(reference__iexact=values["supplier"])
            .exists()
        ):
            errors["supplier"] = "Fournisseur inconnu."
    location = inventory_selectors.locations_of(ctx.organization).filter(name__iexact=values["location"]).first()
    if location is None:
        errors["location"] = "Emplacement inconnu ou archivé."
    if values["quantity"] <= 0:
        errors["quantity"] = "La quantité doit être supérieure à 0."
    if errors or found is None:
        raise ValidationError(errors)
    product, supplier = found
    batch = inventory.create_batch(
        organization=ctx.organization,
        actor=ctx.actor,
        product=product,
        supplier=supplier,
        received_on=values["received_on"],
        unit_cost=values["unit_cost"],
        receipt_reference=OPENING_REFERENCE,
        use_by=values.get("use_by"),
    )
    inventory.post_movement(
        organization=ctx.organization,
        actor=ctx.actor,
        kind=inventory.MovementKind.RECEIPT,
        batch=batch,
        quantity=values["quantity"],
        to_location=location,
        reason="Stock d'ouverture",
    )


def _party(ctx: _Context, key: str, values: Values) -> Any:
    """The customer or the supplier named by reference in a debt row, or None."""
    reference = values.get(key, "")
    if key == "customer":
        return (
            partners_selectors.customers_of(ctx.organization, status="all").filter(reference__iexact=reference).first()
        )
    return partners_selectors.suppliers_of(ctx.organization, status="all").filter(reference__iexact=reference).first()


def _exists_customer_debt(ctx: _Context, values: Values) -> bool:
    customer = _party(ctx, "customer", values)
    if customer is None or "amount" not in values or "owed_on" not in values:
        return False
    return (
        sales_selectors.sales_of(ctx.organization, customer_id=customer.pk)
        .filter(is_opening=True, total=values["amount"], sold_at__date=values["owed_on"])
        .exists()
    )


def _create_customer_debt(ctx: _Context, values: Values) -> None:
    customer = _party(ctx, "customer", values)
    if customer is None:
        raise ValidationError({"customer": "Client inconnu."})
    sales.create_opening_receivable(
        organization=ctx.organization,
        actor=ctx.actor,
        customer=customer,
        amount=values["amount"],
        owed_on=values["owed_on"],
        notes=values.get("notes", ""),
    )


def _exists_supplier_debt(ctx: _Context, values: Values) -> bool:
    supplier = _party(ctx, "supplier", values)
    if supplier is None or "amount" not in values or "invoice_date" not in values:
        return False
    return (
        purchasing_selectors.invoices_of(ctx.organization, supplier_id=supplier.pk)
        .filter(is_opening=True, total=values["amount"], invoice_date=values["invoice_date"])
        .exists()
    )


def _create_supplier_debt(ctx: _Context, values: Values) -> None:
    supplier = _party(ctx, "supplier", values)
    if supplier is None:
        raise ValidationError({"supplier": "Fournisseur inconnu."})
    purchasing.create_opening_invoice(
        organization=ctx.organization,
        actor=ctx.actor,
        supplier=supplier,
        amount=values["amount"],
        invoice_date=values["invoice_date"],
        due_date=values.get("due_date"),
        supplier_reference=values.get("supplier_reference", ""),
        notes=values.get("notes", ""),
    )


# Kinds without a reference column: a row is "already there" when the same document exists (a re-sent file).
_ROW_CHECKS: dict[str, Callable[[_Context, Values], bool]] = {
    "opening_stock": _exists_opening,
    "customer_debts": _exists_customer_debt,
    "supplier_debts": _exists_supplier_debt,
}
_ROW_KEYS: dict[str, tuple[str, ...]] = {
    "opening_stock": ("product", "location", "supplier", "unit_cost", "received_on"),
    "customer_debts": ("customer", "amount", "owed_on"),
    "supplier_debts": ("supplier", "amount", "invoice_date"),
}
# What the report shows in its "Référence" and "Nom" columns for those kinds.
_ROW_LABELS: dict[str, tuple[str, str]] = {
    "opening_stock": ("product", "location"),
    "customer_debts": ("customer", "amount"),
    "supplier_debts": ("supplier", "amount"),
}


@dataclass(frozen=True)
class _Importer:
    exists: Callable[[_Context, str], bool]
    create: Callable[[_Context, Values], None]


_IMPORTERS: dict[str, _Importer] = {
    "products": _Importer(_exists_product, _create_product),
    "suppliers": _Importer(_exists_supplier, _create_supplier),
    "customers": _Importer(_exists_customer, _create_customer),
    "employees": _Importer(_exists_employee, _create_employee),
    "opening_stock": _Importer(lambda _ctx, _reference: False, _create_opening),
    "customer_debts": _Importer(lambda _ctx, _reference: False, _create_customer_debt),
    "supplier_debts": _Importer(lambda _ctx, _reference: False, _create_supplier_debt),
}


def run_import(
    *, organization: Organization, actor: User | None, kind_key: str, content: bytes, dry_run: bool
) -> ImportReport:
    """Read the filled template and create its rows, or only check them with `dry_run`.

    Returns the report, row by row: created, skipped (reference already known) or in error with the column
    and the reason. Nothing is kept for a dry run or when any row is in error. Raises `WorkbookError` for a
    file that cannot be read as this template at all.
    """
    kind = KINDS[kind_key]
    importer = _IMPORTERS[kind_key]
    rows = workbook.read_rows(kind, content)
    report = ImportReport(kind=kind_key, dry_run=dry_run)
    with transaction.atomic():
        ctx = _Context(organization, actor)
        if kind_key == "products":
            ctx.categories = {item.name.casefold(): item for item in catalog_selectors.categories_of(organization)}
        seen: set[str] = set()
        for row in rows:
            values, errors = _parse_cells(kind, row)
            reference = str(values.get("reference", "")).strip()
            entry = RowReport(row.number, CREATED, reference=reference, name=str(values.get("name", "")))
            if kind_key in _ROW_CHECKS:
                ref_key, name_key = _ROW_LABELS[kind_key]
                entry.reference = str(values.get(ref_key, ""))
                entry.name = str(values.get(name_key, ""))
            if not errors and kind_key in _ROW_CHECKS:
                key = "|".join(str(values.get(k, "")).casefold() for k in _ROW_KEYS[kind_key])
                if key in seen:
                    errors.append(ColumnError(kind.columns[0].title, "Cette ligne est déjà plus haut dans le fichier."))
                elif _ROW_CHECKS[kind_key](ctx, values):
                    entry.status = SKIPPED
                seen.add(key)
            elif not errors and reference:
                if reference.casefold() in seen:
                    errors.append(ColumnError("Référence", "Cette référence est déjà plus haut dans le fichier."))
                elif importer.exists(ctx, reference):
                    entry.status = SKIPPED
                seen.add(reference.casefold())
            if not errors and entry.status == CREATED:
                try:
                    with transaction.atomic():
                        importer.create(ctx, values)
                except ValidationError as error:
                    errors = _column_errors(kind, error)
            if errors:
                entry.status = ERROR
                entry.errors = errors
            report.rows.append(entry)
        report.created = sum(1 for item in report.rows if item.status == CREATED)
        report.skipped = sum(1 for item in report.rows if item.status == SKIPPED)
        report.error_count = sum(1 for item in report.rows if item.status == ERROR)
        report.committed = not dry_run and report.error_count == 0
        if not report.committed:
            transaction.set_rollback(True)
    return report
