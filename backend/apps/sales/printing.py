"""What the PDFs of sales documents show (P2-T08, D-071): the template, its data and the document's version.

Registered with the documents app when sales starts (`SalesConfig.ready`). Each provider reads through the
selectors and raises `ObjectDoesNotExist` outside the organization.
"""

from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _

from apps.core.models import Organization
from apps.documents import services as documents

from . import selectors
from .models import CreditNoteKind, CreditNoteStock, InvoiceStatus, QuoteStatus, SalePaymentMethod, SaleStatus
from .payment_selectors import customer_payment_of


def _file_name(prefix: str, number: str) -> str:
    return f"{prefix}-{slugify(number) or 'document'}.pdf"


def _seller_of(organization: Organization) -> dict[str, str]:
    """Who sells, from the finance settings in force (quotes and receipts: nothing is frozen on them)."""
    version = selectors.finance_settings_on(organization)
    if version is None:
        return {"name": organization.name, "address": "", "phone": "", "tax_id": "", "trade_register": ""}
    return {
        "name": version.legal_name or organization.name,
        "address": version.address,
        "phone": version.phone,
        "tax_id": version.tax_id,
        "trade_register": version.trade_register,
    }


def quote_printable(organization: Organization, quote_id: int) -> documents.Printable:
    quote = selectors.quote_of(organization, quote_id)
    context: dict[str, Any] = {
        "number": quote.number,
        "seller": _seller_of(organization),
        "quote": quote,
        "customer": quote.customer,
        "lines": [
            {
                "product_name": line.product.name,
                "quantity": line.quantity,
                "unit_price": line.unit_price,
                "discount_rate": line.discount_rate,
                "amount": line.amount,
            }
            for line in quote.lines.all()
        ],
        # A draft, refused or expired quote says so on the page; a sent or accepted one is clean.
        "status_label": ""
        if quote.current_status in {QuoteStatus.SENT, QuoteStatus.ACCEPTED}  # type: ignore[attr-defined]
        else str(QuoteStatus(quote.current_status).label),  # type: ignore[attr-defined]
    }
    return documents.Printable(
        template="sales/pdf/quote.html",
        context=context,
        version=quote.updated_at.isoformat(),
        filename=_file_name("devis", quote.number),
    )


def invoice_printable(organization: Organization, invoice_id: int) -> documents.Printable:
    invoice = selectors.invoice_of(organization, invoice_id)
    if invoice.status == InvoiceStatus.DRAFT:
        # A draft has no number and may still change: only an issued invoice is a document.
        raise ValidationError(_("Une facture brouillon n'a pas de PDF : émettez-la d'abord."))
    lines = list(invoice.lines.all())
    context: dict[str, Any] = {
        "number": invoice.number,
        "seller": {
            "name": invoice.seller_name,
            "address": invoice.seller_address,
            "phone": invoice.seller_phone,
            "tax_id": invoice.seller_tax_id,
            "trade_register": invoice.seller_trade_register,
        },
        "invoice": invoice,
        "sale_number": invoice.sale.number,
        "lines": lines,
        "has_discount": any(line.discount_rate for line in lines),
        "vat_lines": list(invoice.vat_lines.all()) if invoice.apply_vat else [],
        "cancelled": invoice.status == InvoiceStatus.CANCELLED,
    }
    return documents.Printable(
        template="sales/pdf/invoice.html",
        context=context,
        version=invoice.updated_at.isoformat(),
        filename=_file_name("facture", invoice.number),
    )


def credit_note_printable(organization: Organization, credit_note_id: int) -> documents.Printable:
    note = selectors.credit_notes_of(organization).get(pk=credit_note_id)
    invoice = note.invoice
    context: dict[str, Any] = {
        "number": note.number,
        "seller": {
            "name": invoice.seller_name,
            "address": invoice.seller_address,
            "phone": invoice.seller_phone,
            "tax_id": invoice.seller_tax_id,
            "trade_register": invoice.seller_trade_register,
        },
        "note": note,
        "invoice": invoice,
        "lines": list(note.lines.all()),
        "kind_label": str(CreditNoteKind(note.kind).label),
        "stock_label": "" if note.stock == CreditNoteStock.NONE else str(CreditNoteStock(note.stock).label),
    }
    return documents.Printable(
        template="sales/pdf/credit_note.html",
        context=context,
        version=note.updated_at.isoformat(),
        filename=_file_name("avoir", note.number),
    )


def receipt_printable(organization: Organization, payment_id: int) -> documents.Printable:
    payment = customer_payment_of(organization, payment_id)
    allocations = list(payment.allocations.all())
    allocated = sum((row.amount for row in allocations), Decimal("0.000"))
    rows = []
    for row in allocations:
        invoice = selectors.live_invoice_of(row.sale)
        rows.append(
            {"sale_number": row.sale.number, "invoice_number": invoice.number if invoice else "", "amount": row.amount}
        )
    context: dict[str, Any] = {
        "number": payment.number,
        "seller": _seller_of(organization),
        "payment": payment,
        "customer": payment.customer,
        "method_label": str(SalePaymentMethod(payment.method).label),
        "allocations": rows,
        "unallocated": Decimal("0.000") if payment.voided_at else payment.amount - allocated,
    }
    return documents.Printable(
        template="sales/pdf/receipt.html",
        context=context,
        # Allocating money to sales later does not touch the payment row itself.
        version=f"{payment.updated_at.isoformat()}|{allocated}",
        filename=_file_name("recu", payment.number),
    )


def delivery_note_printable(organization: Organization, sale_id: int) -> documents.Printable:
    """The BL of a validated sale (D-095): what left, at what price, and what the customer owes for it."""
    sale = selectors.sale_of(organization, sale_id)
    if sale.confirmed_at is None:
        # A draft (or a draft given up) has no BL number and moves nothing: validating the sale is what makes the BL.
        raise ValidationError(_("Une vente en brouillon n'a pas de bon de livraison : validez-la d'abord."))
    lines = list(sale.lines.all())
    context: dict[str, Any] = {
        "number": sale.number,
        "seller": _seller_of(organization),
        "sale": sale,
        "sold_on": timezone.localtime(sale.sold_at).date(),
        "customer": sale.customer,
        "location": sale.location,
        "lines": lines,
        "has_discount": any(line.discount_rate for line in lines),
        "total_kg": sum((line.quantity for line in lines), Decimal("0.000")),
        "cancelled": sale.status == SaleStatus.CANCELLED,
    }
    return documents.Printable(
        template="sales/pdf/delivery_note.html",
        context=context,
        version=sale.updated_at.isoformat(),
        filename=_file_name("bl", sale.number),
    )


def register_printables() -> None:
    documents.register(documents.DocumentKind.DELIVERY_NOTE, delivery_note_printable)
    documents.register(documents.DocumentKind.QUOTE, quote_printable)
    documents.register(documents.DocumentKind.INVOICE, invoice_printable)
    documents.register(documents.DocumentKind.CREDIT_NOTE, credit_note_printable)
    documents.register(documents.DocumentKind.RECEIPT, receipt_printable)
