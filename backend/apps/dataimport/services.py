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
from apps.partners import selectors as partners_selectors
from apps.partners import services as partners

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


@dataclass(frozen=True)
class _Importer:
    exists: Callable[[_Context, str], bool]
    create: Callable[[_Context, Values], None]


_IMPORTERS: dict[str, _Importer] = {
    "products": _Importer(_exists_product, _create_product),
    "suppliers": _Importer(_exists_supplier, _create_supplier),
    "customers": _Importer(_exists_customer, _create_customer),
    "employees": _Importer(_exists_employee, _create_employee),
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
            if not errors and reference:
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
