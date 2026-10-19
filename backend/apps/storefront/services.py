"""Every write on the public site's requests goes through these functions (ARCHITECTURE §3, D-186)."""

import datetime as dt
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.catalog import selectors as catalog
from apps.core import audit
from apps.core.models import Organization, User

from . import selectors
from .models import SiteProduct, SiteSettings, WebRequest, WebRequestKind, WebRequestLine, WebRequestStatus

MAX_LINES = 30
# A line above this is a typing slip, not a restaurant's order.
MAX_LINE_QUANTITY = Decimal("10000")
_SEPARATORS = re.compile(r"[\s.\-/()]")


def normalize_phone(raw: str) -> str:
    """A phone number the office can call back, written one way.

    Tunisian numbers have 8 digits, with or without +216 / 00216: they come back as "+216 98 123 456". A foreign
    number must start with + or 00 and have 8 to 15 digits; it comes back as "+33612345678".
    """
    value = _SEPARATORS.sub("", raw.strip())
    if value.startswith("00"):
        value = "+" + value[2:]
    if value.startswith("+216"):
        value = value[4:]
    if value.isdigit() and len(value) == 8 and value[0] in "234579":
        return f"+216 {value[:2]} {value[2:5]} {value[5:]}"
    if value.startswith("+") and value[1:].isdigit() and 8 <= len(value) - 1 <= 15 and not value.startswith("+216"):
        return value
    raise ValidationError({"phone": _("Numéro de téléphone invalide : 8 chiffres, par exemple 98 123 456.")})


@dataclass(frozen=True)
class RequestedLine:
    product_id: int
    quantity: Decimal
    note: str = ""


@transaction.atomic
def submit_web_request(
    *,
    organization: Organization,
    kind: str,
    full_name: str,
    phone: str,
    lines: Sequence[RequestedLine],
    email: str = "",
    company: str = "",
    city: str = "",
    address: str = "",
    wanted_on: dt.date | None = None,
    message: str = "",
) -> WebRequest:
    """A visitor's quote request or order. The phone number is required and checked; an order needs at least one
    product, a quote request a product or a message. Each product must be one the company sells today.

    The office is told at once (notifications, D-175) through the audit entry; nothing moves stock or money."""
    errors: dict[str, str] = {}
    full_name = full_name.strip()
    if not full_name:
        errors["full_name"] = _("Indiquez votre nom.")
    try:
        phone = normalize_phone(phone)
    except ValidationError as error:
        errors.update({field: messages[0] for field, messages in error.message_dict.items()})
    if kind not in WebRequestKind.values:
        errors["kind"] = _("Type de demande inconnu.")
    if len(lines) > MAX_LINES:
        errors["lines"] = _("Au plus %(count)s produits par demande.") % {"count": MAX_LINES}
    elif kind == WebRequestKind.ORDER and not lines:
        errors["lines"] = _("Ajoutez au moins un produit à la commande.")
    elif kind == WebRequestKind.QUOTE and not lines and not message.strip():
        errors["lines"] = _("Ajoutez un produit ou écrivez votre besoin dans le message.")
    if wanted_on is not None and wanted_on < timezone.localdate():
        errors["wanted_on"] = _("La date souhaitée est déjà passée.")

    offered = {offer.product_id: offer for offer in selectors.site_products(organization)}
    seen: set[int] = set()
    for line in lines:
        if line.quantity <= 0 or line.quantity > MAX_LINE_QUANTITY:
            errors["lines"] = _("Chaque quantité doit être entre 0 et %(max)s kg.") % {"max": MAX_LINE_QUANTITY}
            break
        if line.product_id in seen:
            errors["lines"] = _("Un même produit est demandé deux fois.")
            break
        seen.add(line.product_id)
        if line.product_id not in offered:
            errors["lines"] = _("Un produit demandé n'est plus proposé sur le site.")
            break
    if errors:
        raise ValidationError(errors)

    request = WebRequest.objects.create(
        organization=organization,
        kind=kind,
        full_name=full_name,
        phone=phone,
        email=email.strip(),
        company=company.strip(),
        city=city.strip(),
        address=address.strip(),
        wanted_on=wanted_on,
        message=message.strip(),
    )
    WebRequestLine.objects.bulk_create(
        WebRequestLine(
            organization=organization,
            request=request,
            product=offered[line.product_id].product,
            quantity=line.quantity,
            web_price=offered[line.product_id].web_price,
            note=line.note.strip(),
        )
        for line in lines
    )
    audit.record(
        organization=organization,
        actor=None,
        action="web_request.received",
        target=request,
        after={"kind": kind, "phone": phone, "lines": len(lines)},
    )
    return request


@transaction.atomic
def set_web_request_status(*, request: WebRequest, actor: User, status: str, note: str = "") -> WebRequest:
    """The office called the visitor back: the request is handled or cancelled, with what was agreed. A closed
    request may be opened again (status "new") when the visitor calls back."""
    if status not in WebRequestStatus.values:
        raise ValidationError({"status": _("Statut inconnu.")})
    request = WebRequest.objects.select_for_update().get(pk=request.pk)
    before = {"status": request.status, "office_note": request.office_note}
    request.status = status
    request.office_note = note.strip()
    if status == WebRequestStatus.NEW:
        request.handled_by, request.handled_at = None, None
    else:
        request.handled_by, request.handled_at = actor, timezone.now()
    request.save(update_fields=["status", "office_note", "handled_by", "handled_at", "updated_at"])
    audit.record(
        organization=request.organization,
        actor=actor,
        action="web_request.status_changed",
        target=request,
        before=before,
        after={"status": request.status, "office_note": request.office_note},
    )
    return request


# ---- What the site shows: the office chooses the products and their web price (D-186) ----


def _checked_web_price(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if value <= 0:
        raise ValidationError({"web_price": _("Le prix du site doit être positif, ou vide pour « prix sur demande ».")})
    return value


def _site_values(site_product: SiteProduct) -> dict[str, object]:
    return {
        "is_published": site_product.is_published,
        "web_price": site_product.web_price,
        "description": site_product.description,
        "position": site_product.position,
    }


SITE_FIELDS = frozenset({"web_price", "description", "is_published", "position"})


@transaction.atomic
def update_site_product(
    *, organization: Organization, actor: User, product_id: int, changes: Mapping[str, Any]
) -> SiteProduct:
    """Change what the site shows of one active product: hide or show it, its web price (None: "prix sur
    demande"), its text or its place. Only the fields named in `changes` change; the product itself, its day's
    price and its price lists stay as they are."""
    unknown = set(changes) - SITE_FIELDS
    if unknown:
        raise ValidationError({"detail": _("Champ inconnu : %(fields)s.") % {"fields": ", ".join(sorted(unknown))}})
    try:
        product = catalog.product_of(organization, product_id)
    except ObjectDoesNotExist:
        raise ValidationError({"product": _("Produit inconnu.")}) from None
    if not product.is_active:
        raise ValidationError({"product": _("Ce produit est archivé : il n'est pas montré sur le site.")})
    site_product, _created = SiteProduct.objects.select_for_update().get_or_create(
        organization=organization, product=product, defaults={"position": selectors.UNORDERED}
    )
    before = _site_values(site_product)
    if "web_price" in changes:
        site_product.web_price = _checked_web_price(changes["web_price"])
    if "description" in changes:
        site_product.description = str(changes["description"]).strip()
    if "is_published" in changes:
        site_product.is_published = bool(changes["is_published"])
    if "position" in changes:
        site_product.position = int(changes["position"])
    site_product.save()
    audit.record(
        organization=organization,
        actor=actor,
        action="site_product.changed",
        target=site_product,
        before=before,
        after={"product": product.name, **_site_values(site_product)},
    )
    return site_product


# ---- How visitors reach the company (D-186) ----


def _settings_values(site_settings: SiteSettings) -> dict[str, str]:
    return {
        "phone": site_settings.phone,
        "whatsapp": site_settings.whatsapp,
        "email": site_settings.email,
        "address": site_settings.address,
        "opening_hours": site_settings.opening_hours,
    }


@transaction.atomic
def save_site_settings(
    *,
    organization: Organization,
    actor: User,
    phone: str = "",
    whatsapp: str = "",
    email: str = "",
    address: str = "",
    opening_hours: str = "",
) -> SiteSettings:
    """Set the phone, WhatsApp, e-mail, address and hours the public site shows. The numbers are checked and written
    one way, like a visitor's (`normalize_phone`); an empty field hides that line on the site."""
    errors: dict[str, str] = {}
    numbers: dict[str, str] = {}
    for field, value in (("phone", phone), ("whatsapp", whatsapp)):
        if not value.strip():
            numbers[field] = ""
            continue
        try:
            numbers[field] = normalize_phone(value)
        except ValidationError:
            errors[field] = _("Numéro de téléphone invalide : 8 chiffres, par exemple 74 123 456.")
    if errors:
        raise ValidationError(errors)
    site_settings, _created = SiteSettings.objects.select_for_update().get_or_create(organization=organization)
    before = _settings_values(site_settings)
    site_settings.phone = numbers["phone"]
    site_settings.whatsapp = numbers["whatsapp"]
    site_settings.email = email.strip()
    site_settings.address = address.strip()
    site_settings.opening_hours = opening_hours.strip()
    site_settings.save()
    audit.record(
        organization=organization,
        actor=actor,
        action="site_settings.changed",
        target=site_settings,
        before=before,
        after=_settings_values(site_settings),
    )
    return site_settings
