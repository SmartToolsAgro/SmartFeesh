"""Every write on suppliers goes through these functions (ARCHITECTURE §3)."""

import re
from collections.abc import Sequence
from typing import Any, TypedDict, Unpack

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils.translation import gettext as _

from apps.core import audit
from apps.core.models import Organization, User

from .models import Supplier, SupplierContact

SUPPLIER_REFERENCE_PREFIX = "F-"
_GENERATED_REFERENCE = re.compile(rf"^{SUPPLIER_REFERENCE_PREFIX}(\d+)$", re.IGNORECASE)
# 7 digits and a key letter, then the VAT code, the category and the establishment number (000 = head office).
_TAX_ID = re.compile(r"^(\d{6,7})([A-Z])(?:([A-Z])([A-Z])(\d{3}))?$")


class SupplierFields(TypedDict, total=False):
    reference: str
    name: str
    tax_id: str
    phone: str
    email: str
    address: str
    city: str
    notes: str


class ContactFields(TypedDict, total=False):
    name: str
    role: str
    phone: str
    email: str


def normalized_tax_id(value: str) -> str:
    """A Tunisian tax ID ("matricule fiscal") written the usual way: `1234567A/A/M/000`, or `1234567A` alone.

    Spaces, dots, dashes and slashes are ignored when reading it, and an old 6-digit number gets its
    leading zero back. Raises ValueError when it does not have that shape. Empty stays empty.
    """
    compact = re.sub(r"[\s./-]", "", value.upper())
    if not compact:
        return ""
    match = _TAX_ID.match(compact)
    if match is None:
        raise ValueError(_("Matricule fiscal invalide : attendu 1234567A/A/M/000 ou 1234567A."))
    number, key, vat_code, category, establishment = match.groups()
    identifier = f"{number.zfill(7)}{key}"
    return f"{identifier}/{vat_code}/{category}/{establishment}" if vat_code else identifier


def _next_reference(organization: Organization) -> str:
    """F-001, F-002... one more than the highest reference of that shape in the organization."""
    numbers = [
        int(match.group(1))
        for reference in Supplier.objects.for_organization(organization).values_list("reference", flat=True)
        if (match := _GENERATED_REFERENCE.match(reference))
    ]
    return f"{SUPPLIER_REFERENCE_PREFIX}{max(numbers, default=0) + 1:03d}"


def _snapshot(supplier: Supplier, contacts: Sequence[SupplierContact]) -> dict[str, Any]:
    return {
        "reference": supplier.reference,
        "name": supplier.name,
        "tax_id": supplier.tax_id,
        "phone": supplier.phone,
        "email": supplier.email,
        "address": supplier.address,
        "city": supplier.city,
        "notes": supplier.notes,
        "contacts": [
            {"name": contact.name, "role": contact.role, "phone": contact.phone, "email": contact.email}
            for contact in contacts
        ],
    }


def _email_error(value: str) -> bool:
    try:
        validate_email(value)
    except ValidationError:
        return True
    return False


def _clean_supplier(supplier: Supplier) -> None:
    """Business rules shared by creation and update. Raises ValidationError with one message per field."""
    errors: dict[str, str] = {}
    for field in ("reference", "name", "phone", "email", "address", "city", "notes"):
        setattr(supplier, field, getattr(supplier, field).strip())
    others = Supplier.objects.for_organization(supplier.organization).exclude(pk=supplier.pk)
    if not supplier.reference:
        errors["reference"] = _("La référence est obligatoire.")
    elif others.filter(reference__iexact=supplier.reference).exists():
        errors["reference"] = _("Un autre fournisseur porte déjà cette référence.")
    if not supplier.name:
        errors["name"] = _("Le nom est obligatoire.")
    try:
        supplier.tax_id = normalized_tax_id(supplier.tax_id)
    except ValueError as error:
        errors["tax_id"] = str(error)
    else:
        if supplier.tax_id and others.filter(tax_id=supplier.tax_id).exists():
            errors["tax_id"] = _("Un autre fournisseur a déjà ce matricule fiscal.")
    if supplier.email and _email_error(supplier.email):
        errors["email"] = _("Adresse e-mail invalide.")
    if errors:
        raise ValidationError(errors)


def _cleaned_contacts(supplier: Supplier, contacts: Sequence[ContactFields]) -> list[SupplierContact]:
    cleaned = []
    for number, fields in enumerate(contacts, start=1):
        contact = SupplierContact(
            organization=supplier.organization,
            supplier=supplier,
            name=fields.get("name", "").strip(),
            role=fields.get("role", "").strip(),
            phone=fields.get("phone", "").strip(),
            email=fields.get("email", "").strip(),
        )
        if not contact.name:
            raise ValidationError({"contacts": _("Contact %(number)s : le nom est obligatoire.") % {"number": number}})
        if contact.email and _email_error(contact.email):
            raise ValidationError({"contacts": _("Contact %(number)s : adresse e-mail invalide.") % {"number": number}})
        cleaned.append(contact)
    return cleaned


@transaction.atomic
def create_supplier(
    *,
    organization: Organization,
    actor: User | None,
    contacts: Sequence[ContactFields] = (),
    **fields: Unpack[SupplierFields],
) -> Supplier:
    """A new supplier. Without a reference it gets the next free `F-NNN`."""
    # Serializes creations in one organization, so two of them cannot take the same generated reference.
    Organization.objects.select_for_update().filter(pk=organization.pk).first()
    supplier = Supplier(organization=organization, **fields)
    if not supplier.reference.strip():
        supplier.reference = _next_reference(organization)
    _clean_supplier(supplier)
    new_contacts = _cleaned_contacts(supplier, contacts)
    supplier.save()
    SupplierContact.objects.bulk_create(new_contacts)
    audit.record(
        organization=organization,
        actor=actor,
        action="supplier.created",
        target=supplier,
        after=_snapshot(supplier, new_contacts),
    )
    return supplier


@transaction.atomic
def update_supplier(
    *,
    supplier: Supplier,
    actor: User | None,
    contacts: Sequence[ContactFields] | None = None,
    **fields: Unpack[SupplierFields],
) -> Supplier:
    """Change a supplier. `contacts`, when given, replaces the whole list; absent, the list is kept."""
    supplier = Supplier.objects.select_for_update().get(pk=supplier.pk)
    old_contacts = list(supplier.contacts.order_by("id"))
    before = _snapshot(supplier, old_contacts)
    for field, value in fields.items():
        setattr(supplier, field, value)
    _clean_supplier(supplier)
    new_contacts = old_contacts if contacts is None else _cleaned_contacts(supplier, contacts)
    supplier.save()
    if contacts is not None:
        supplier.contacts.all().delete()
        SupplierContact.objects.bulk_create(new_contacts)
    after = _snapshot(supplier, new_contacts)
    changed = [field for field in after if after[field] != before[field]]
    if changed:
        audit.record(
            organization=supplier.organization,
            actor=actor,
            action="supplier.updated",
            target=supplier,
            before={field: before[field] for field in changed},
            after={field: after[field] for field in changed},
        )
    return supplier


@transaction.atomic
def set_supplier_active(*, supplier: Supplier, actor: User | None, is_active: bool) -> Supplier:
    """Archive a supplier (it keeps its history but is no longer bought from), or bring it back."""
    supplier = Supplier.objects.select_for_update().get(pk=supplier.pk)
    if supplier.is_active != is_active:
        supplier.is_active = is_active
        supplier.save(update_fields=["is_active", "updated_at"])
        action = "supplier.restored" if is_active else "supplier.archived"
        audit.record(organization=supplier.organization, actor=actor, action=action, target=supplier)
    return supplier
