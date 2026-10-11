"""Every write on purchases goes through these functions (ARCHITECTURE §3)."""

import datetime as dt
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, TypedDict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core import audit
from apps.core.models import Organization, User
from apps.core.money import Number, checked_amount, checked_quantity
from apps.inventory import services as inventory
from apps.inventory.services import MovementKind

from .models import GoodsReceipt, GoodsReceiptLine, ReceiptCounter

if TYPE_CHECKING:
    from apps.catalog.models import Product
    from apps.inventory.models import StockLocation
    from apps.partners.models import Supplier

RECEIPT_NUMBER_PREFIX = "BR-"


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
) -> GoodsReceipt:
    """Record goods received from a supplier: one batch per line, and its accepted weight into stock.

    Everything is checked before anything is written; problems come back together, the header's on
    their field and each line's on `lines.<index>.<field>`. The receipt, its batches and its movements
    are saved in one transaction, so a refused receipt leaves nothing behind.
    """
    errors = _header_errors(organization, supplier, location, received_on)
    if not lines:
        errors["lines"] = _("Ajoutez au moins un produit.")
    checked_lines = [_checked_line(organization, index, line, received_on, errors) for index, line in enumerate(lines)]
    if errors:
        raise ValidationError(errors)

    supplier_reference = supplier_reference.strip()
    receipt = GoodsReceipt.objects.create(
        organization=organization,
        number=_next_receipt_number(organization),
        supplier=supplier,
        location=location,
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
    audit.record(
        organization=organization,
        actor=actor,
        action="receipt.created",
        target=receipt,
        after=_snapshot(receipt, saved),
    )
    return receipt
