"""The statement PDF of a customer or a supplier ("fiche client", "fiche fournisseur", D-156).

For a period (`date_from` to `date_to`) or up to a day (`date_from` empty: from the beginning): every sale or
receipt with its products, kilos and prices, every payment, the account with the balance carried in and out, the
returnable boxes, and a summary at the top. Made on the spot (`documents.services.render_pdf`), never stored: it
depends on the dates the person asks for.
"""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.utils import timezone
from django.utils.text import slugify

from apps.boxes import selectors as boxes
from apps.core.models import Organization
from apps.core.money import money
from apps.documents import services as documents
from apps.partners import selectors as partners
from apps.purchasing import selectors as purchasing
from apps.sales import selectors as sales

ZERO = Decimal("0.000")


@dataclass(frozen=True)
class ProductTotal:
    reference: str
    name: str
    quantity: Decimal
    amount: Decimal
    # The amount over the kilos, to the millime; empty without kilos.
    average_price: Decimal | None


def _seller_of(organization: Organization) -> dict[str, str]:
    version = sales.finance_settings_on(organization)
    if version is None:
        return {"name": organization.name, "address": "", "phone": "", "tax_id": "", "trade_register": ""}
    return {
        "name": version.legal_name or organization.name,
        "address": version.address,
        "phone": version.phone,
        "tax_id": version.tax_id,
        "trade_register": version.trade_register,
    }


def _party(label: str, party: Any) -> dict[str, str]:
    return {
        "label": label,
        "name": party.name,
        "reference": party.reference,
        "address": ", ".join(part for part in (party.address, party.city) if part),
        "phone": party.phone,
        "tax_id": party.tax_id,
    }


def _by_product(lines: list[tuple[str, str, Decimal, Decimal]]) -> list[ProductTotal]:
    """(reference, name, kilos, amount) added up per product, most kilos first."""
    totals: dict[tuple[str, str], list[Decimal]] = defaultdict(lambda: [ZERO, ZERO])
    for reference, name, quantity, amount in lines:
        totals[(reference, name)][0] += quantity
        totals[(reference, name)][1] += amount
    rows = [
        ProductTotal(
            reference=reference,
            name=name,
            quantity=quantity,
            amount=amount,
            average_price=money(amount / quantity) if quantity else None,
        )
        for (reference, name), (quantity, amount) in totals.items()
    ]
    rows.sort(key=lambda row: (-row.quantity, row.name))
    return rows


def _period(date_from: dt.date | None, date_to: dt.date) -> str:
    if date_from is None:
        return f"Jusqu'au {date_to:%d/%m/%Y} (depuis le début)"
    return f"Du {date_from:%d/%m/%Y} au {date_to:%d/%m/%Y}"


def _ledger(entries: Any) -> list[dict[str, Any]]:
    """Account rows with the amount in the debit or the credit column."""
    return [
        {
            "entry": entry,
            "debit": entry.amount if entry.amount > 0 else None,
            "credit": -entry.amount if entry.amount < 0 else None,
        }
        for entry in entries
    ]


def _file_name(prefix: str, party: Any, date_to: dt.date) -> str:
    return f"{prefix}-{slugify(party.reference) or party.pk}-{slugify(party.name)}-{date_to:%Y-%m-%d}.pdf"


def customer_statement_printable(
    organization: Organization, customer_id: int, *, date_from: dt.date | None, date_to: dt.date
) -> documents.Printable:
    """Raises ObjectDoesNotExist for a customer outside the organization."""
    customer = partners.customer_of(organization, customer_id)
    statement = sales.customer_statement(organization, customer.pk, date_from=date_from, date_to=date_to)
    box_figures = boxes.party_boxes(organization, customer_id=customer.pk, date_from=date_from, date_to=date_to)
    lines = [
        (line.product_reference, line.product_name, line.quantity, line.amount)
        for sale in statement.sales
        for line in sale.lines
    ]
    sold = sum((entry.amount for entry in statement.entries if entry.kind == "sale"), ZERO)
    paid = -sum((entry.amount for entry in statement.entries if entry.kind != "sale"), ZERO)
    context: dict[str, Any] = {
        "number": customer.reference,
        "seller": _seller_of(organization),
        "doc_date": date_to,
        "party": _party("Client", customer),
        "period": _period(date_from, date_to),
        "printed_at": timezone.localtime(),
        "statement": statement,
        "ledger": _ledger(statement.entries),
        "products": _by_product(lines),
        "summary": {
            "opening": statement.opening_balance,
            "sold": sold,
            "paid": paid,
            "closing": statement.closing_balance,
            "closing_abs": abs(statement.closing_balance),
            "sales_count": sum(1 for sale in statement.sales if not sale.is_opening),
            "quantity": sum((sale.quantity for sale in statement.sales), ZERO),
            "lines_total": sum((sale.total for sale in statement.sales), ZERO),
        },
        "boxes": box_figures,
    }
    return documents.Printable(
        template="reports/pdf/customer_statement.html",
        context=context,
        version="",
        filename=_file_name("releve-client", customer, date_to),
    )


def supplier_statement_printable(
    organization: Organization, supplier_id: int, *, date_from: dt.date | None, date_to: dt.date
) -> documents.Printable:
    """Raises ObjectDoesNotExist for a supplier outside the organization."""
    supplier = partners.supplier_of(organization, supplier_id)
    statement = purchasing.supplier_statement(organization, supplier.pk, date_from=date_from, date_to=date_to)
    box_figures = boxes.party_boxes(organization, supplier_id=supplier.pk, date_from=date_from, date_to=date_to)
    lines = [
        (line.product_reference, line.product_name, line.invoiced_quantity, line.amount)
        for receipt in statement.receipts
        for line in receipt.lines
    ]
    invoiced = sum((entry.amount for entry in statement.entries if entry.kind == "invoice"), ZERO)
    paid = -sum((entry.amount for entry in statement.entries if entry.kind == "payment"), ZERO)
    context: dict[str, Any] = {
        "number": supplier.reference,
        "seller": _seller_of(organization),
        "doc_date": date_to,
        "party": _party("Fournisseur", supplier),
        "period": _period(date_from, date_to),
        "printed_at": timezone.localtime(),
        "statement": statement,
        "ledger": _ledger(statement.entries),
        "products": _by_product(lines),
        "summary": {
            "opening": statement.opening_balance,
            "invoiced": invoiced,
            "paid": paid,
            "closing": statement.closing_balance,
            "closing_abs": abs(statement.closing_balance),
            "receipts_count": len(statement.receipts),
            "quantity": sum((receipt.quantity for receipt in statement.receipts), ZERO),
            "received_total": sum((receipt.total for receipt in statement.receipts), ZERO),
            "uninvoiced": statement.uninvoiced_total,
        },
        "boxes": box_figures,
    }
    return documents.Printable(
        template="reports/pdf/supplier_statement.html",
        context=context,
        version="",
        filename=_file_name("releve-fournisseur", supplier, date_to),
    )
