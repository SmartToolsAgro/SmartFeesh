"""Every write on purchases goes through these functions (ARCHITECTURE §3)."""

import datetime as dt
from collections.abc import Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Any, TypedDict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core import audit
from apps.core.models import Organization, User
from apps.core.money import Number, checked_amount, checked_quantity
from apps.inventory import services as inventory
from apps.inventory.services import MovementKind

from . import selectors
from .models import (
    RECEIVABLE_ORDER_STATUSES,
    DocumentCounter,
    DocumentKind,
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    ReceiptCounter,
    SupplierInvoice,
    SupplierInvoiceReceipt,
    SupplierInvoiceStatus,
    SupplierPayment,
    SupplierPaymentAllocation,
)
from .models import PaymentMethod as PaymentMethod  # re-exported for apps that record payments (the demo)

if TYPE_CHECKING:
    from apps.catalog.models import Product
    from apps.inventory.models import StockLocation
    from apps.partners.models import Supplier

RECEIPT_NUMBER_PREFIX = "BR-"
INVOICE_NUMBER_PREFIX = "FF-"
ORDER_NUMBER_PREFIX = "BA-"
PAYMENT_NUMBER_PREFIX = "RF-"


class ReceiptLineFields(TypedDict, total=False):
    product: "Product"
    ordered_quantity: Number | None
    invoiced_quantity: Number
    accepted_quantity: Number
    unit_cost: Number
    use_by: dt.date | None


def line_error_key(index: int, field: str) -> str:
    """Errors of a line are reported on `lines.<index>.<field>`, so each one shows under its own input."""
    return f"lines.{index}.{field}"


def _next_receipt_number(organization: Organization) -> str:
    """BR-0001, BR-0002... per organization, taken under a row lock (same scheme as batch numbers, D-034)."""
    ReceiptCounter.objects.bulk_create([ReceiptCounter(organization=organization)], ignore_conflicts=True)
    counter = ReceiptCounter.objects.select_for_update().get(organization=organization)
    counter.last_number += 1
    counter.save(update_fields=["last_number"])
    return f"{RECEIPT_NUMBER_PREFIX}{counter.last_number:04d}"


def _header_errors(
    organization: Organization, supplier: "Supplier", location: "StockLocation", received_on: dt.date
) -> dict[str, str]:
    errors: dict[str, str] = {}
    if supplier.organization_id != organization.pk:
        errors["supplier"] = _("Fournisseur inconnu.")
    elif not supplier.is_active:
        errors["supplier"] = _("Ce fournisseur est archivé.")
    if location.organization_id != organization.pk:
        errors["location"] = _("Emplacement inconnu.")
    elif not location.is_active:
        errors["location"] = _("Cet emplacement est archivé.")
    if received_on > timezone.localdate():
        errors["received_on"] = _("La date de réception ne peut pas être dans le futur.")
    return errors


def _checked_line(
    organization: Organization, index: int, line: ReceiptLineFields, received_on: dt.date, errors: dict[str, str]
) -> dict[str, Any]:
    """The line's values once checked; every problem is added to `errors` under the line's own keys."""
    checked: dict[str, Any] = {"product": line.get("product"), "use_by": line.get("use_by")}
    product = checked["product"]
    if product is None or product.organization_id != organization.pk:
        errors[line_error_key(index, "product")] = _("Produit inconnu.")
    elif not product.is_active:
        errors[line_error_key(index, "product")] = _("Ce produit est archivé.")
    for field in ("invoiced_quantity", "accepted_quantity"):
        try:
            value: Any = line.get(field, "")
            checked[field] = checked_quantity(value)
        except (ValueError, TypeError):
            errors[line_error_key(index, field)] = _("Indiquez un poids net en kg, supérieur à zéro.")
    ordered = line.get("ordered_quantity")
    checked["ordered_quantity"] = None
    if ordered not in (None, ""):
        try:
            checked["ordered_quantity"] = checked_quantity(ordered)
        except (ValueError, TypeError):
            errors[line_error_key(index, "ordered_quantity")] = _("Indiquez un poids en kg, ou laissez vide.")
    try:
        cost: Any = line.get("unit_cost", "")
        checked["unit_cost"] = checked_amount(cost)
    except (ValueError, TypeError):
        errors[line_error_key(index, "unit_cost")] = _("Indiquez un coût en DT par kg, au millime près.")
    use_by = checked["use_by"]
    if use_by is not None and use_by < received_on:
        errors[line_error_key(index, "use_by")] = _("La date limite ne peut pas précéder la réception.")
    return checked


def _snapshot(receipt: GoodsReceipt, lines: Sequence[GoodsReceiptLine]) -> dict[str, Any]:
    return {
        "number": receipt.number,
        "purchase_order": receipt.purchase_order.number if receipt.purchase_order else None,
        "supplier": receipt.supplier.reference,
        "location": receipt.location.name,
        "received_on": receipt.received_on.isoformat(),
        "supplier_reference": receipt.supplier_reference,
        "lines": [
            {
                "batch": line.batch.number,
                "product": line.product.reference,
                "ordered_quantity": str(line.ordered_quantity) if line.ordered_quantity is not None else None,
                "invoiced_quantity": str(line.invoiced_quantity),
                "accepted_quantity": str(line.accepted_quantity),
                "unit_cost": str(line.unit_cost),
            }
            for line in lines
        ],
    }


@transaction.atomic
def create_receipt(
    *,
    organization: Organization,
    actor: User | None,
    supplier: "Supplier",
    location: "StockLocation",
    received_on: dt.date,
    lines: Sequence[ReceiptLineFields],
    supplier_reference: str = "",
    notes: str = "",
    purchase_order: PurchaseOrder | None = None,
) -> GoodsReceipt:
    """Record goods received from a supplier: one batch per line, and its accepted weight into stock.

    Everything is checked before anything is written; problems come back together, the header's on
    their field and each line's on `lines.<index>.<field>`. The receipt, its batches and its movements
    are saved in one transaction, so a refused receipt leaves nothing behind.

    Against a purchase order (D-076) the receipt may carry only some of its products and only part of
    their weight: the order stays open until every line is delivered or it is closed by hand. A line's
    product must be on the order; its accepted weight counts as received there.
    """
    errors = _header_errors(organization, supplier, location, received_on)
    order = _locked_order_to_receive(organization, supplier, purchase_order, errors) if purchase_order else None
    order_lines = {line.product_id: line for line in order.lines.all()} if order else {}
    if not lines:
        errors["lines"] = _("Ajoutez au moins un produit.")
    checked_lines = [_checked_line(organization, index, line, received_on, errors) for index, line in enumerate(lines)]
    if order:
        for index, values in enumerate(checked_lines):
            product = values["product"]
            if product is not None and product.pk not in order_lines:
                errors[line_error_key(index, "product")] = _("Ce produit n'est pas sur le bon d'achat %(number)s.") % {
                    "number": order.number
                }
            # The order says what was asked for; a delivery of part of it is not a difference.
            values["ordered_quantity"] = None
    if errors:
        raise ValidationError(errors)

    supplier_reference = supplier_reference.strip()
    receipt = GoodsReceipt.objects.create(
        organization=organization,
        number=_next_receipt_number(organization),
        supplier=supplier,
        location=location,
        purchase_order=order,
        received_on=received_on,
        supplier_reference=supplier_reference,
        notes=notes.strip(),
        created_by=actor,
    )
    # Received today: now. Typed later for an earlier day: noon of that day keeps the ledger in date order.
    occurred_at = (
        timezone.now()
        if received_on == timezone.localdate()
        else timezone.make_aware(dt.datetime.combine(received_on, dt.time(12, 0)))
    )
    saved: list[GoodsReceiptLine] = []
    for values in checked_lines:
        batch = inventory.create_batch(
            organization=organization,
            actor=actor,
            product=values["product"],
            supplier=supplier,
            received_on=received_on,
            unit_cost=values["unit_cost"],
            receipt_reference=supplier_reference or receipt.number,
            use_by=values["use_by"],
        )
        line = GoodsReceiptLine.objects.create(
            organization=organization,
            receipt=receipt,
            product=values["product"],
            batch=batch,
            order_line=order_lines.get(values["product"].pk),
            ordered_quantity=values["ordered_quantity"],
            invoiced_quantity=values["invoiced_quantity"],
            accepted_quantity=values["accepted_quantity"],
            unit_cost=values["unit_cost"],
        )
        inventory.post_movement(
            organization=organization,
            actor=actor,
            kind=MovementKind.RECEIPT,
            batch=batch,
            quantity=values["accepted_quantity"],
            to_location=location,
            source=line,
            occurred_at=occurred_at,
        )
        saved.append(line)
    if order:
        refresh_order_status(order)
    audit.record(
        organization=organization,
        actor=actor,
        action="receipt.created",
        target=receipt,
        after=_snapshot(receipt, saved),
    )
    return receipt


# ---- Purchase orders, the "bon d'achat" (D-076) ----
# An order moves no stock and owes nothing; its receipts do. Its status follows them.


class OrderLineFields(TypedDict, total=False):
    product: "Product"
    ordered_quantity: Number
    unit_cost: Number


def _next_order_number(organization: Organization) -> str:
    DocumentCounter.objects.bulk_create(
        [DocumentCounter(organization=organization, kind=DocumentKind.PURCHASE_ORDER)], ignore_conflicts=True
    )
    counter = DocumentCounter.objects.select_for_update().get(
        organization=organization, kind=DocumentKind.PURCHASE_ORDER
    )
    counter.last_number += 1
    counter.save(update_fields=["last_number"])
    return f"{ORDER_NUMBER_PREFIX}{counter.last_number:04d}"


def _order_snapshot(order: PurchaseOrder) -> dict[str, Any]:
    return {
        "number": order.number,
        "supplier": order.supplier.reference,
        "ordered_on": order.ordered_on.isoformat(),
        "expected_on": order.expected_on.isoformat() if order.expected_on else None,
        "status": order.status,
        "lines": {
            line.product.reference: {"ordered_quantity": str(line.ordered_quantity), "unit_cost": str(line.unit_cost)}
            for line in order.lines.select_related("product")
        },
    }


@transaction.atomic
def create_order(
    *,
    organization: Organization,
    actor: User | None,
    supplier: "Supplier",
    ordered_on: dt.date,
    lines: Sequence[OrderLineFields],
    expected_on: dt.date | None = None,
    notes: str = "",
) -> PurchaseOrder:
    """Record what we ask a supplier to deliver: products, weights and agreed prices.

    Every problem comes back at once, the header's on their field and each line's on
    `lines.<index>.<field>`. A product appears once per order.
    """
    errors: dict[str, str] = {}
    if supplier.organization_id != organization.pk:
        errors["supplier"] = _("Fournisseur inconnu.")
    elif not supplier.is_active:
        errors["supplier"] = _("Ce fournisseur est archivé.")
    if ordered_on > timezone.localdate():
        errors["ordered_on"] = _("La date du bon d'achat ne peut pas être dans le futur.")
    if expected_on is not None and expected_on < ordered_on:
        errors["expected_on"] = _("La livraison prévue ne peut pas précéder le bon d'achat.")
    if not lines:
        errors["lines"] = _("Ajoutez au moins un produit.")
    checked_lines: list[dict[str, Any]] = []
    seen: set[int] = set()
    for index, line in enumerate(lines):
        product = line.get("product")
        checked: dict[str, Any] = {"product": product}
        if product is None or product.organization_id != organization.pk:
            errors[line_error_key(index, "product")] = _("Produit inconnu.")
        elif not product.is_active:
            errors[line_error_key(index, "product")] = _("Ce produit est archivé.")
        elif product.pk in seen:
            errors[line_error_key(index, "product")] = _("Ce produit est déjà sur le bon d'achat.")
        else:
            seen.add(product.pk)
        try:
            value: Any = line.get("ordered_quantity", "")
            checked["ordered_quantity"] = checked_quantity(value)
        except (ValueError, TypeError):
            errors[line_error_key(index, "ordered_quantity")] = _("Indiquez un poids net en kg, supérieur à zéro.")
        try:
            cost: Any = line.get("unit_cost", "")
            checked["unit_cost"] = checked_amount(cost)
        except (ValueError, TypeError):
            errors[line_error_key(index, "unit_cost")] = _("Indiquez un prix en DT par kg, au millime près.")
        checked_lines.append(checked)
    if errors:
        raise ValidationError(errors)

    order = PurchaseOrder.objects.create(
        organization=organization,
        number=_next_order_number(organization),
        supplier=supplier,
        ordered_on=ordered_on,
        expected_on=expected_on,
        notes=notes.strip(),
        created_by=actor,
    )
    PurchaseOrderLine.objects.bulk_create(
        [PurchaseOrderLine(organization=organization, order=order, **values) for values in checked_lines]
    )
    audit.record(
        organization=organization,
        actor=actor,
        action="purchase_order.created",
        target=order,
        after=_order_snapshot(order),
    )
    return order


def _locked_order(order: PurchaseOrder) -> PurchaseOrder:
    return (
        PurchaseOrder.objects.select_for_update(of=("self",))
        .select_related("supplier")
        .prefetch_related("lines")
        .get(pk=order.pk)
    )


def _locked_order_to_receive(
    organization: Organization, supplier: "Supplier", order: PurchaseOrder, errors: dict[str, str]
) -> PurchaseOrder | None:
    """The order re-read under a row lock so two deliveries cannot be counted at once; problems go to `errors`."""
    if order.organization_id != organization.pk:
        errors["purchase_order"] = _("Bon d'achat inconnu.")
        return None
    locked = _locked_order(order)
    if locked.supplier_id != supplier.pk:
        errors["purchase_order"] = _("Le bon d'achat %(number)s est d'un autre fournisseur.") % {
            "number": locked.number
        }
    elif locked.status not in RECEIVABLE_ORDER_STATUSES:
        errors["purchase_order"] = _("Le bon d'achat %(number)s est %(status)s : on ne peut plus y recevoir.") % {
            "number": locked.number,
            "status": PurchaseOrderStatus(locked.status).label.lower(),
        }
    return locked


def refresh_order_status(order: PurchaseOrder) -> PurchaseOrder:
    """Set the status from what was received: nothing → open; every line in full → received; else partly.

    Only an order still waiting for goods changes; a closed or cancelled one stays as it was decided.
    """
    if order.status not in RECEIVABLE_ORDER_STATUSES:
        return order
    received = {
        row["order_line"]: row["total"]
        for row in GoodsReceiptLine.objects.filter(order_line__order=order)
        .values("order_line")
        .annotate(total=Sum("accepted_quantity"))
    }
    lines = list(order.lines.all())
    if lines and all(received.get(line.pk, Decimal("0")) >= line.ordered_quantity for line in lines):
        status = PurchaseOrderStatus.RECEIVED
    elif received:
        status = PurchaseOrderStatus.PARTLY_RECEIVED
    else:
        status = PurchaseOrderStatus.OPEN
    if status != order.status:
        order.status = status
        order.save(update_fields=["status", "updated_at"])
    return order


@transaction.atomic
def cancel_order(*, order: PurchaseOrder, actor: User | None) -> PurchaseOrder:
    """Cancel an order nothing was delivered against. Once goods came, it is closed instead."""
    order = _locked_order(order)
    if order.receipts.exists():
        raise ValidationError(
            _("Le bon d'achat %(number)s a déjà reçu des marchandises : clôturez-le au lieu de l'annuler.")
            % {"number": order.number}
        )
    if order.status != PurchaseOrderStatus.OPEN:
        raise ValidationError(_("Le bon d'achat %(number)s ne peut plus être annulé.") % {"number": order.number})
    before = _order_snapshot(order)
    order.status = PurchaseOrderStatus.CANCELLED
    order.closed_at = timezone.now()
    order.save(update_fields=["status", "closed_at", "updated_at"])
    audit.record(
        organization=order.organization,
        actor=actor,
        action="purchase_order.cancelled",
        target=order,
        before=before,
        after=_order_snapshot(order),
    )
    return order


@transaction.atomic
def close_order(*, order: PurchaseOrder, actor: User | None) -> PurchaseOrder:
    """Close an order partly delivered: the rest will not come. What was received stays as received."""
    order = _locked_order(order)
    if order.status != PurchaseOrderStatus.PARTLY_RECEIVED:
        raise ValidationError(
            _("Seul un bon d'achat reçu en partie peut être clôturé : %(number)s est %(status)s.")
            % {"number": order.number, "status": PurchaseOrderStatus(order.status).label.lower()}
        )
    before = _order_snapshot(order)
    order.status = PurchaseOrderStatus.CLOSED
    order.closed_at = timezone.now()
    order.save(update_fields=["status", "closed_at", "updated_at"])
    audit.record(
        organization=order.organization,
        actor=actor,
        action="purchase_order.closed",
        target=order,
        before=before,
        after=_order_snapshot(order),
    )
    return order


# ---- Supplier invoices and payments (P1-T08, D-043) ----
# A trade payable only: a partner's capital and profit share are separate balances (D-040, Phase 6).


def _next_document_number(organization: Organization, kind: DocumentKind, prefix: str) -> str:
    """FF-0001 for invoices, RF-0001 for payments... per organization, taken under a row lock."""
    DocumentCounter.objects.bulk_create([DocumentCounter(organization=organization, kind=kind)], ignore_conflicts=True)
    counter = DocumentCounter.objects.select_for_update().get(organization=organization, kind=kind)
    counter.last_number += 1
    counter.save(update_fields=["last_number"])
    return f"{prefix}{counter.last_number:04d}"


def _invoice_header_errors(
    organization: Organization, supplier: "Supplier", invoice_date: dt.date, due_date: dt.date
) -> dict[str, str]:
    errors: dict[str, str] = {}
    # An archived supplier is still owed what was bought from them: invoices and payments stay possible.
    if supplier.organization_id != organization.pk:
        errors["supplier"] = _("Fournisseur inconnu.")
    if invoice_date > timezone.localdate():
        errors["invoice_date"] = _("La date de facture ne peut pas être dans le futur.")
    if due_date < invoice_date:
        errors["due_date"] = _("L'échéance ne peut pas précéder la date de facture.")
    return errors


def _locked_receipts(
    organization: Organization,
    supplier: "Supplier",
    receipts: Sequence[GoodsReceipt],
    errors: dict[str, str],
    invoice: SupplierInvoice | None = None,
) -> list[GoodsReceipt]:
    """The receipts to charge, locked so two invoices cannot take the same one; problems go to `errors`."""
    if not receipts:
        errors["receipts"] = _("Choisissez au moins une réception.")
        return []
    ids = sorted({receipt.pk for receipt in receipts})
    locked = list(
        GoodsReceipt.objects.select_for_update(of=("self",))
        .filter(pk__in=ids)
        .order_by("received_on", "id")
        .select_related("invoice_link__invoice")
        .prefetch_related("lines")
    )
    problems: list[str] = []
    for receipt in locked:
        if receipt.organization_id != organization.pk:
            problems.append(_("Réception inconnue."))
        elif receipt.supplier_id != supplier.pk:
            problems.append(_("La réception %(number)s est d'un autre fournisseur.") % {"number": receipt.number})
        else:
            link = getattr(receipt, "invoice_link", None)
            if link is not None and (invoice is None or link.invoice_id != invoice.pk):
                problems.append(
                    _("La réception %(number)s est déjà sur la facture %(invoice)s.")
                    % {"number": receipt.number, "invoice": link.invoice.number}
                )
    if len(locked) != len(ids):
        problems.append(_("Réception inconnue."))
    if problems:
        errors["receipts"] = " ".join(dict.fromkeys(problems))
    return locked


def _set_receipts(invoice: SupplierInvoice, receipts: Sequence[GoodsReceipt]) -> None:
    """Charge exactly these receipts on the invoice, and keep its total as the sum of their amounts."""
    SupplierInvoiceReceipt.objects.filter(invoice=invoice).delete()
    links = [
        SupplierInvoiceReceipt(
            organization_id=invoice.organization_id,
            invoice=invoice,
            receipt=receipt,
            # What the supplier charges for the receipt: invoiced kg × cost per line (D-039).
            amount=selectors.receipt_totals(receipt)[0],
        )
        for receipt in receipts
    ]
    SupplierInvoiceReceipt.objects.bulk_create(links)
    invoice.total = sum((link.amount for link in links), Decimal("0.000"))
    invoice.save(update_fields=["total", "updated_at"])


def _invoice_snapshot(invoice: SupplierInvoice) -> dict[str, Any]:
    links = SupplierInvoiceReceipt.objects.filter(invoice=invoice).select_related("receipt").order_by("receipt_id")
    return {
        "number": invoice.number,
        "supplier": invoice.supplier.reference,
        "supplier_reference": invoice.supplier_reference,
        "invoice_date": invoice.invoice_date.isoformat(),
        "due_date": invoice.due_date.isoformat(),
        "status": invoice.status,
        "total": str(invoice.total),
        "receipts": {link.receipt.number: str(link.amount) for link in links},
    }


def _post(invoice: SupplierInvoice, actor: User | None) -> None:
    if invoice.total <= 0:
        raise ValidationError({"receipts": _("Le montant de la facture est nul : il n'y a rien à valider.")})
    invoice.status = SupplierInvoiceStatus.POSTED
    invoice.posted_at = timezone.now()
    invoice.posted_by = actor
    invoice.save(update_fields=["status", "posted_at", "posted_by", "updated_at"])
    audit.record(
        organization=invoice.organization,
        actor=actor,
        action="supplier_invoice.posted",
        target=invoice,
        after=_invoice_snapshot(invoice),
    )


def _locked_draft(invoice: SupplierInvoice) -> SupplierInvoice:
    """The invoice re-read under a row lock; refused unless it is still a draft."""
    locked = SupplierInvoice.objects.select_for_update().select_related("supplier", "organization").get(pk=invoice.pk)
    if locked.status != SupplierInvoiceStatus.DRAFT:
        raise ValidationError(
            _("La facture %(number)s est validée : elle ne se modifie plus.") % {"number": locked.number}
        )
    return locked


@transaction.atomic
def create_invoice(
    *,
    organization: Organization,
    actor: User | None,
    supplier: "Supplier",
    receipts: Sequence[GoodsReceipt],
    invoice_date: dt.date,
    due_date: dt.date,
    supplier_reference: str = "",
    notes: str = "",
    post: bool = False,
) -> SupplierInvoice:
    """Record a supplier's invoice for some of their receipts, as a draft, or posted at once with `post`.

    Its amount is the receipts' invoiced amount; a receipt goes on one invoice only. Every problem comes
    back at once, on its field.
    """
    errors = _invoice_header_errors(organization, supplier, invoice_date, due_date)
    locked = _locked_receipts(organization, supplier, receipts, errors) if "supplier" not in errors else []
    if errors:
        raise ValidationError(errors)
    invoice = SupplierInvoice.objects.create(
        organization=organization,
        number=_next_document_number(organization, DocumentKind.SUPPLIER_INVOICE, INVOICE_NUMBER_PREFIX),
        supplier=supplier,
        supplier_reference=supplier_reference.strip(),
        invoice_date=invoice_date,
        due_date=due_date,
        notes=notes.strip(),
        created_by=actor,
    )
    _set_receipts(invoice, locked)
    audit.record(
        organization=organization,
        actor=actor,
        action="supplier_invoice.created",
        target=invoice,
        after=_invoice_snapshot(invoice),
    )
    if post:
        _post(invoice, actor)
    return invoice


@transaction.atomic
def update_invoice(
    *,
    invoice: SupplierInvoice,
    actor: User | None,
    receipts: Sequence[GoodsReceipt],
    invoice_date: dt.date,
    due_date: dt.date,
    supplier_reference: str = "",
    notes: str = "",
    post: bool = False,
) -> SupplierInvoice:
    """Change a draft invoice (its receipts, dates, reference, notes); with `post`, post it afterwards.

    The supplier does not change: a draft for the wrong supplier is deleted and typed again.
    """
    invoice = _locked_draft(invoice)
    organization = invoice.organization
    errors = _invoice_header_errors(organization, invoice.supplier, invoice_date, due_date)
    locked = _locked_receipts(organization, invoice.supplier, receipts, errors, invoice=invoice)
    if errors:
        raise ValidationError(errors)
    before = _invoice_snapshot(invoice)
    invoice.supplier_reference = supplier_reference.strip()
    invoice.invoice_date = invoice_date
    invoice.due_date = due_date
    invoice.notes = notes.strip()
    invoice.save(update_fields=["supplier_reference", "invoice_date", "due_date", "notes", "updated_at"])
    _set_receipts(invoice, locked)
    audit.record(
        organization=organization,
        actor=actor,
        action="supplier_invoice.updated",
        target=invoice,
        before=before,
        after=_invoice_snapshot(invoice),
    )
    if post:
        _post(invoice, actor)
    return invoice


@transaction.atomic
def post_invoice(*, invoice: SupplierInvoice, actor: User | None) -> SupplierInvoice:
    """Post a draft: it is now owed to the supplier, counts in their balance and can be paid. Final."""
    invoice = _locked_draft(invoice)
    _post(invoice, actor)
    return invoice


@transaction.atomic
def delete_invoice(*, invoice: SupplierInvoice, actor: User | None) -> None:
    """Delete a draft invoice; its receipts can go on another invoice. A posted invoice is never deleted."""
    invoice = _locked_draft(invoice)
    audit.record(
        organization=invoice.organization,
        actor=actor,
        action="supplier_invoice.deleted",
        target=invoice,
        before=_invoice_snapshot(invoice),
    )
    invoice.delete()


class AllocationFields(TypedDict):
    invoice: SupplierInvoice
    amount: Number


def allocation_error_key(index: int, field: str) -> str:
    """Errors of an allocation are reported on `allocations.<index>.<field>`, like receipt lines."""
    return f"allocations.{index}.{field}"


def _paid_on(invoice: SupplierInvoice) -> Decimal:
    paid = SupplierPaymentAllocation.objects.filter(invoice=invoice).aggregate(total=Sum("amount"))["total"]
    return paid if paid is not None else Decimal("0.000")


def _checked_allocations(
    organization: Organization,
    supplier: "Supplier",
    allocations: Sequence[AllocationFields],
    available: Decimal | None,
    errors: dict[str, str],
) -> list[tuple[SupplierInvoice, Decimal]]:
    """The allocations once checked, their invoices locked; every problem is added to `errors`.

    `available` is what the payment can still allocate, or None when its own amount was refused.
    """
    ids = sorted({line["invoice"].pk for line in allocations})
    invoices = {
        invoice.pk: invoice for invoice in SupplierInvoice.objects.select_for_update().filter(pk__in=ids).order_by("id")
    }
    checked: list[tuple[SupplierInvoice, Decimal]] = []
    seen: set[int] = set()
    for index, line in enumerate(allocations):
        invoice = invoices.get(line["invoice"].pk)
        invoice_key = allocation_error_key(index, "invoice")
        if invoice is None or invoice.organization_id != organization.pk:
            errors[invoice_key] = _("Facture inconnue.")
            continue
        if invoice.supplier_id != supplier.pk:
            errors[invoice_key] = _("Cette facture est d'un autre fournisseur.")
            continue
        if invoice.pk in seen:
            errors[invoice_key] = _("Cette facture est déjà dans la liste.")
            continue
        seen.add(invoice.pk)
        if invoice.status == SupplierInvoiceStatus.DRAFT:
            errors[invoice_key] = _("Cette facture est un brouillon : validez-la avant de la payer.")
            continue
        if invoice.status == SupplierInvoiceStatus.PAID:
            errors[invoice_key] = _("Cette facture est déjà payée.")
            continue
        amount_key = allocation_error_key(index, "amount")
        try:
            value: Any = line.get("amount", "")
            amount = checked_amount(value)
        except (ValueError, TypeError):
            errors[amount_key] = _("Indiquez un montant en DT, au millime près.")
            continue
        if amount == 0:
            errors[amount_key] = _("Le montant doit être supérieur à zéro.")
            continue
        remaining = invoice.total - _paid_on(invoice)
        if amount > remaining:
            errors[amount_key] = _("Il ne reste que %(remaining)s DT à payer sur cette facture.") % {
                "remaining": remaining
            }
            continue
        checked.append((invoice, amount))
    allocated = sum((amount for _invoice, amount in checked), Decimal("0.000"))
    if available is not None and allocated > available:
        errors["allocations"] = _(
            "Les affectations (%(allocated)s DT) dépassent le montant disponible (%(available)s DT)."
        ) % {
            "allocated": allocated,
            "available": available,
        }
    return checked


def _allocate(
    payment: SupplierPayment, actor: User | None, allocations: Sequence[tuple[SupplierInvoice, Decimal]]
) -> None:
    for invoice, amount in allocations:
        SupplierPaymentAllocation.objects.create(
            organization_id=payment.organization_id, payment=payment, invoice=invoice, amount=amount, created_by=actor
        )
        paid = _paid_on(invoice)
        invoice.status = SupplierInvoiceStatus.PAID if paid >= invoice.total else SupplierInvoiceStatus.PARTLY_PAID
        invoice.save(update_fields=["status", "updated_at"])


def _payment_snapshot(payment: SupplierPayment) -> dict[str, Any]:
    allocations = SupplierPaymentAllocation.objects.filter(payment=payment).select_related("invoice").order_by("id")
    return {
        "number": payment.number,
        "supplier": payment.supplier.reference,
        "paid_on": payment.paid_on.isoformat(),
        "amount": str(payment.amount),
        "method": payment.method,
        "reference": payment.reference,
        "allocations": [{"invoice": line.invoice.number, "amount": str(line.amount)} for line in allocations],
    }


@transaction.atomic
def record_payment(
    *,
    organization: Organization,
    actor: User | None,
    supplier: "Supplier",
    paid_on: dt.date,
    amount: Number,
    method: str,
    allocations: Sequence[AllocationFields] = (),
    reference: str = "",
    notes: str = "",
) -> SupplierPayment:
    """Record money paid to a supplier and the posted invoices it settles.

    The allocations may cover all of the amount, part of it or none: what is left is an advance, already
    deducted from the supplier balance, to allocate later (`allocate_payment`). An allocation never goes
    beyond what is left to pay on its invoice. Every problem comes back at once, on its field.
    """
    errors: dict[str, str] = {}
    if supplier.organization_id != organization.pk:
        errors["supplier"] = _("Fournisseur inconnu.")
    if paid_on > timezone.localdate():
        errors["paid_on"] = _("La date du paiement ne peut pas être dans le futur.")
    if method not in PaymentMethod.values:
        errors["method"] = _("Mode de paiement inconnu.")
    checked: Decimal | None = None
    try:
        checked = checked_amount(amount)
        if checked == 0:
            checked = None
            errors["amount"] = _("Le montant doit être supérieur à zéro.")
    except (ValueError, TypeError):
        errors["amount"] = _("Indiquez un montant en DT, au millime près.")
    allocated = (
        _checked_allocations(organization, supplier, allocations, checked, errors) if "supplier" not in errors else []
    )
    if errors:
        raise ValidationError(errors)
    assert checked is not None  # an amount error would have been raised above
    payment = SupplierPayment.objects.create(
        organization=organization,
        number=_next_document_number(organization, DocumentKind.SUPPLIER_PAYMENT, PAYMENT_NUMBER_PREFIX),
        supplier=supplier,
        paid_on=paid_on,
        amount=checked,
        method=method,
        reference=reference.strip(),
        notes=notes.strip(),
        created_by=actor,
    )
    _allocate(payment, actor, allocated)
    audit.record(
        organization=organization,
        actor=actor,
        action="supplier_payment.recorded",
        target=payment,
        after=_payment_snapshot(payment),
    )
    return payment


@transaction.atomic
def allocate_payment(
    *, payment: SupplierPayment, actor: User | None, allocations: Sequence[AllocationFields]
) -> SupplierPayment:
    """Allocate the part of a payment not allocated yet (an advance) to posted invoices of its supplier."""
    payment = SupplierPayment.objects.select_for_update().select_related("supplier", "organization").get(pk=payment.pk)
    errors: dict[str, str] = {}
    if not allocations:
        errors["allocations"] = _("Choisissez au moins une facture.")
    already = SupplierPaymentAllocation.objects.filter(payment=payment).aggregate(total=Sum("amount"))["total"]
    available = payment.amount - (already if already is not None else Decimal("0.000"))
    checked = _checked_allocations(payment.organization, payment.supplier, allocations, available, errors)
    if errors:
        raise ValidationError(errors)
    before = _payment_snapshot(payment)
    _allocate(payment, actor, checked)
    audit.record(
        organization=payment.organization,
        actor=actor,
        action="supplier_payment.allocated",
        target=payment,
        before=before,
        after=_payment_snapshot(payment),
    )
    return payment
