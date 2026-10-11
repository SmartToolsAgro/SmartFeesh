"""Every write on sales documents goes through these functions (ARCHITECTURE §3)."""

import datetime as dt
import uuid
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, TypedDict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _

from apps.catalog import selectors as catalog
from apps.core import audit
from apps.core.models import Organization, User
from apps.core.money import Number, checked_amount, checked_quantity, line_total, money

from . import selectors
from .models import DocumentCounter, Quote, QuoteLine, QuoteStatus

if TYPE_CHECKING:
    from apps.catalog.models import Product
    from apps.inventory.models import StockLocation
    from apps.partners.models import Customer

# ---- Quotes (P2-T03, D-050) ----

QUOTE_SERIES = "DV"
# Validity when none is given: the prototype's quote is "valable 3 jours". Provisional (D-050): seafood
# prices move daily, so a short validity is the safe default.
DEFAULT_VALIDITY_DAYS = 3
MAX_DISCOUNT_RATE = Decimal("100")
_RATE_STEP = Decimal("0.01")


class QuoteLineFields(TypedDict, total=False):
    product: "Product"
    quantity: Number
    # DT per kg; empty takes the sale price in force on the quote's day.
    unit_price: Number | None
    # Percent with at most 2 decimals; empty means none.
    discount_rate: Number | None


def line_error_key(index: int, field: str) -> str:
    """Errors of a document line are reported on `lines.<index>.<field>`, under the line's own input."""
    return f"lines.{index}.{field}"


def _next_number(organization: Organization, series: str) -> str:
    """DV-0001, DV-0002... per organization and series, taken under a row lock (same scheme as batches).

    Taken in the transaction that creates the document and quotes are never deleted, so there are no gaps.
    """
    DocumentCounter.objects.bulk_create(
        [DocumentCounter(organization=organization, series=series)], ignore_conflicts=True
    )
    counter = DocumentCounter.objects.select_for_update().get(organization=organization, series=series)
    counter.last_number += 1
    counter.save(update_fields=["last_number"])
    return f"{series}-{counter.last_number:04d}"


def moment_of(day: dt.date) -> dt.datetime:
    """The moment whose sale prices a quote of `day` uses: now when it is today, noon of that day otherwise."""
    if day == timezone.localdate():
        return timezone.now()
    return timezone.make_aware(dt.datetime.combine(day, dt.time(12, 0)))


def _header_errors(
    organization: Organization,
    customer: "Customer",
    location: "StockLocation | None",
    quoted_on: dt.date,
    valid_until: dt.date,
) -> dict[str, str]:
    errors: dict[str, str] = {}
    if customer.organization_id != organization.pk:
        errors["customer"] = _("Client inconnu.")
    elif not customer.is_active:
        errors["customer"] = _("Ce client est archivé.")
    if location is not None:
        if location.organization_id != organization.pk:
            errors["location"] = _("Emplacement inconnu.")
        elif not location.is_active:
            errors["location"] = _("« %(name)s » est archivé.") % {"name": location.name}
    if quoted_on > timezone.localdate():
        errors["quoted_on"] = _("La date du devis ne peut pas être dans le futur.")
    if valid_until < quoted_on:
        errors["valid_until"] = _("La date de validité ne peut pas précéder la date du devis.")
    return errors


def _checked_price(product: "Product | None", price: Any, at: dt.datetime, customer: "Customer") -> Decimal | str:
    """The price per kg of a line, or the message saying why there is none.

    Empty takes what the customer is charged at `at` (`catalog.price_in_force`, D-049): their own price
    list when it holds the product, else the daily price. A typed price must be above zero.
    """
    if price in (None, ""):
        in_force = catalog.price_in_force(product, at, customer_id=customer.pk) if product is not None else None
        if in_force is None:
            return _("Aucun prix de vente en vigueur : indiquez un prix.")
        return in_force.price
    try:
        amount = checked_amount(price)
    except (ValueError, TypeError):
        amount = None
    if amount is None or amount <= 0:
        return _("Indiquez un prix en DT par kg, supérieur à zéro, au millime près.")
    return amount


def _checked_rate(rate: Any) -> Decimal | None:
    """A discount in percent, from 0 to 100 with at most 2 decimals; None when it is not one."""
    if rate in (None, ""):
        return Decimal("0.00")
    if isinstance(rate, bool) or not isinstance(rate, Decimal | int | str):
        return None
    try:
        value = Decimal(rate)
    except InvalidOperation:
        return None
    if not value.is_finite() or value != value.quantize(_RATE_STEP) or not 0 <= value <= MAX_DISCOUNT_RATE:
        return None
    return value.quantize(_RATE_STEP)


def priced_line(quantity: Decimal, unit_price: Decimal, discount_rate: Decimal) -> dict[str, Decimal]:
    """The amounts of a line: gross = kg × price, discount = gross × rate / 100, each rounded once to the
    millime (half up), and amount = gross − discount."""
    gross = line_total(quantity, unit_price)
    discount = money(gross * discount_rate / 100)
    return {"gross_amount": gross, "discount_amount": discount, "amount": gross - discount}


def _checked_lines(
    organization: Organization,
    customer: "Customer",
    lines: Sequence[QuoteLineFields],
    at: dt.datetime,
    errors: dict[str, str],
) -> list[dict[str, Any]]:
    """The lines' values once checked and priced; each problem is added to `errors` under the line's keys."""
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
            errors[line_error_key(index, "product")] = _("Ce produit est déjà sur une autre ligne.")
        else:
            seen.add(product.pk)
        try:
            value: Any = line.get("quantity", "")
            checked["quantity"] = checked_quantity(value)
        except (ValueError, TypeError):
            errors[line_error_key(index, "quantity")] = _("Indiquez un poids en kg, supérieur à zéro.")
        if line_error_key(index, "product") not in errors:
            price = _checked_price(product, line.get("unit_price"), at, customer)
            if isinstance(price, Decimal):
                checked["unit_price"] = price
            else:
                errors[line_error_key(index, "unit_price")] = price
        rate = _checked_rate(line.get("discount_rate"))
        if rate is None:
            errors[line_error_key(index, "discount_rate")] = _(
                "Indiquez une remise en %, de 0 à 100, avec 2 décimales au plus."
            )
        checked["discount_rate"] = rate
        if "quantity" in checked and "unit_price" in checked and rate is not None:
            checked.update(priced_line(checked["quantity"], checked["unit_price"], rate))
        checked_lines.append(checked)
    return checked_lines


def _prepared(
    organization: Organization,
    customer: "Customer",
    location: "StockLocation | None",
    quoted_on: dt.date,
    valid_until: dt.date | None,
    lines: Sequence[QuoteLineFields],
) -> tuple[dt.date, list[dict[str, Any]]]:
    """The validity date and the checked lines of a quote, or a ValidationError with every problem at once."""
    if valid_until is None:
        valid_until = quoted_on + dt.timedelta(days=DEFAULT_VALIDITY_DAYS)
    errors = _header_errors(organization, customer, location, quoted_on, valid_until)
    if not lines:
        errors["lines"] = _("Ajoutez au moins un produit.")
    checked_lines = _checked_lines(organization, customer, lines, moment_of(quoted_on), errors)
    if errors:
        raise ValidationError(errors)
    return valid_until, checked_lines


def _write_lines(quote: Quote, checked_lines: list[dict[str, Any]]) -> None:
    """Replace the lines and set the quote's totals from them (no VAT yet: P2-T05)."""
    QuoteLine.objects.bulk_create(
        [
            QuoteLine(
                organization_id=quote.organization_id,
                quote=quote,
                product=values["product"],
                quantity=values["quantity"],
                unit_price=values["unit_price"],
                discount_rate=values["discount_rate"],
                gross_amount=values["gross_amount"],
                discount_amount=values["discount_amount"],
                amount=values["amount"],
            )
            for values in checked_lines
        ]
    )
    quote.subtotal = sum((values["gross_amount"] for values in checked_lines), Decimal("0.000"))
    quote.discount_total = sum((values["discount_amount"] for values in checked_lines), Decimal("0.000"))
    quote.total_excl_tax = quote.subtotal - quote.discount_total
    # P2-T05 hook: VAT comes from the organization's finance settings (D-018) once they exist.
    quote.tax_amount = None
    quote.total = quote.total_excl_tax
    quote.save(update_fields=["subtotal", "discount_total", "total_excl_tax", "tax_amount", "total", "updated_at"])


def _snapshot(quote: Quote) -> dict[str, Any]:
    return {
        "number": quote.number,
        "status": quote.status,
        "customer": quote.customer.reference,
        "location": quote.location.name if quote.location is not None else None,
        "quoted_on": quote.quoted_on.isoformat(),
        "valid_until": quote.valid_until.isoformat(),
        "lines": [
            {
                "product": line.product.reference,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "discount_rate": str(line.discount_rate),
                "amount": str(line.amount),
            }
            for line in quote.lines.select_related("product").order_by("id")
        ],
        "total": str(quote.total),
    }


@transaction.atomic
def create_quote(
    *,
    organization: Organization,
    actor: User | None,
    customer: "Customer",
    quoted_on: dt.date,
    lines: Sequence[QuoteLineFields],
    valid_until: dt.date | None = None,
    location: "StockLocation | None" = None,
    notes: str = "",
    client_uuid: uuid.UUID | None = None,
    send: bool = False,
) -> Quote:
    """Prepare a quote as a draft; with `send`, also mark it sent (one transaction).

    A line without a price takes the sale price in force on the quote's day; the price is then kept on
    the line. Without a validity date the quote is valid `DEFAULT_VALIDITY_DAYS` days. A `client_uuid`
    already used returns that quote.
    """
    if client_uuid is not None:
        existing = Quote.objects.for_organization(organization).filter(client_uuid=client_uuid).first()
        if existing is not None:
            return existing
    valid_until, checked_lines = _prepared(organization, customer, location, quoted_on, valid_until, lines)
    quote = Quote.objects.create(
        organization=organization,
        number=_next_number(organization, QUOTE_SERIES),
        customer=customer,
        location=location,
        quoted_on=quoted_on,
        valid_until=valid_until,
        notes=notes.strip(),
        created_by=actor,
        client_uuid=client_uuid,
    )
    _write_lines(quote, checked_lines)
    audit.record(organization=organization, actor=actor, action="quote.created", target=quote, after=_snapshot(quote))
    if send:
        return send_quote(quote=quote, actor=actor)
    return quote


def _locked(quote: Quote) -> Quote:
    """The quote locked until commit, so two answers recorded at once never both apply."""
    return (
        Quote.objects.select_for_update(of=("self",))
        .select_related("organization", "customer", "location")
        .get(pk=quote.pk)
    )


def _status_name(quote: Quote) -> str:
    return str(QuoteStatus(quote.status).label).lower()


def _locked_draft(quote: Quote) -> Quote:
    locked = _locked(quote)
    if locked.status != QuoteStatus.DRAFT:
        raise ValidationError(_("Ce devis est %(status)s : il ne se modifie plus.") % {"status": _status_name(locked)})
    return locked


@transaction.atomic
def update_quote(
    *,
    quote: Quote,
    actor: User | None,
    customer: "Customer",
    quoted_on: dt.date,
    lines: Sequence[QuoteLineFields],
    valid_until: dt.date | None = None,
    location: "StockLocation | None" = None,
    notes: str = "",
    send: bool = False,
) -> Quote:
    """Change a draft: customer, place, dates, notes and lines (all replaced). With `send`, send it too."""
    quote = _locked_draft(quote)
    organization = quote.organization
    before = _snapshot(quote)
    valid_until, checked_lines = _prepared(organization, customer, location, quoted_on, valid_until, lines)
    quote.customer = customer
    quote.location = location
    quote.quoted_on = quoted_on
    quote.valid_until = valid_until
    quote.notes = notes.strip()
    quote.save()
    quote.lines.all().delete()
    _write_lines(quote, checked_lines)
    audit.record(
        organization=organization,
        actor=actor,
        action="quote.updated",
        target=quote,
        before=before,
        after=_snapshot(quote),
    )
    if send:
        return send_quote(quote=quote, actor=actor)
    return quote


def _expiry_error(quote: Quote) -> ValidationError:
    return ValidationError(
        {
            "valid_until": _("Ce devis n'est plus valable depuis le %(date)s : faites un nouveau devis.")
            % {"date": date_format(quote.valid_until, "SHORT_DATE_FORMAT")}
        }
    )


@transaction.atomic
def send_quote(*, quote: Quote, actor: User | None) -> Quote:
    """Mark a draft as given to the customer: from now on it no longer changes. Refused when its validity
    date has already passed or its customer was archived meanwhile."""
    quote = _locked_draft(quote)
    if quote.valid_until < timezone.localdate():
        raise _expiry_error(quote)
    if not quote.customer.is_active:
        raise ValidationError({"customer": _("Ce client est archivé.")})
    quote.status = QuoteStatus.SENT
    quote.sent_by = actor
    quote.sent_at = timezone.now()
    quote.save(update_fields=["status", "sent_by", "sent_at", "updated_at"])
    audit.record(organization=quote.organization, actor=actor, action="quote.sent", target=quote)
    return quote


def _locked_sent(quote: Quote) -> Quote:
    locked = _locked(quote)
    if locked.status == QuoteStatus.DRAFT:
        raise ValidationError(_("Envoyez d'abord ce devis au client."))
    if locked.status != QuoteStatus.SENT:
        raise ValidationError(_("Ce devis est déjà %(status)s.") % {"status": _status_name(locked)})
    return locked


@transaction.atomic
def accept_quote(*, quote: Quote, actor: User | None) -> Quote:
    """Record the customer's yes on a sent quote, up to its validity date included. The accepted quote
    keeps its prices and becomes a sale in P2-T04; no stock is reserved."""
    quote = _locked_sent(quote)
    if quote.valid_until < timezone.localdate():
        raise _expiry_error(quote)
    quote.status = QuoteStatus.ACCEPTED
    quote.answered_by = actor
    quote.answered_at = timezone.now()
    quote.save(update_fields=["status", "answered_by", "answered_at", "updated_at"])
    audit.record(organization=quote.organization, actor=actor, action="quote.accepted", target=quote)
    return quote


@transaction.atomic
def refuse_quote(*, quote: Quote, actor: User | None, reason: str = "") -> Quote:
    """Record the customer's no on a sent quote, with an optional reason (too dear, bought elsewhere...).
    Allowed after the validity date too: the answer is worth keeping."""
    quote = _locked_sent(quote)
    quote.status = QuoteStatus.REFUSED
    quote.answered_by = actor
    quote.answered_at = timezone.now()
    quote.refusal_reason = reason.strip()[:255]
    quote.save(update_fields=["status", "answered_by", "answered_at", "refusal_reason", "updated_at"])
    audit.record(
        organization=quote.organization,
        actor=actor,
        action="quote.refused",
        target=quote,
        after={"reason": quote.refusal_reason},
    )
    return quote


@transaction.atomic
def expire_quotes(*, organization: Organization, actor: User | None = None, today: dt.date | None = None) -> int:
    """Mark as expired the sent quotes whose validity date is before `today` (the nightly job). Returns
    how many. The screens already show them expired before this runs (`selectors.current_quote_status`)."""
    today = today or timezone.localdate()
    now = timezone.now()
    expired = 0
    for quote in selectors.quotes_to_expire(organization, today=today).select_for_update().order_by("id"):
        quote.status = QuoteStatus.EXPIRED
        quote.expired_at = now
        quote.save(update_fields=["status", "expired_at", "updated_at"])
        audit.record(organization=organization, actor=actor, action="quote.expired", target=quote)
        expired += 1
    return expired
