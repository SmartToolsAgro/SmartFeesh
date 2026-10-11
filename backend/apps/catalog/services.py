"""Every write on the catalogue goes through these functions (ARCHITECTURE §3)."""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, TypedDict, Unpack

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core import audit
from apps.core.images import reencoded_photo
from apps.core.models import Organization, User
from apps.core.money import Number, checked_quantity, money
from apps.partners import selectors as partner_selectors

from . import selectors
from .models import Category, Illustration, PriceList, PriceListItem, Product, ProductPrice


class ProductFields(TypedDict, total=False):
    reference: str
    name: str
    name_ar: str
    category: Category
    min_stock: Number
    storage_temp_min: Decimal | None
    storage_temp_max: Decimal | None
    illustration: str


def _snapshot(product: Product) -> dict[str, Any]:
    return {
        "reference": product.reference,
        "name": product.name,
        "name_ar": product.name_ar,
        "category": product.category.name,
        "min_stock": product.min_stock,
        "storage_temp_min": product.storage_temp_min,
        "storage_temp_max": product.storage_temp_max,
        "illustration": product.illustration,
    }


def _check_category_name(organization: Organization, name: str, *, exclude: Category | None = None) -> str:
    name = name.strip()
    if not name:
        raise ValidationError({"name": _("Le nom est obligatoire.")})
    others = Category.objects.for_organization(organization).filter(name__iexact=name)
    if exclude is not None:
        others = others.exclude(pk=exclude.pk)
    if others.exists():
        raise ValidationError({"name": _("Une catégorie porte déjà ce nom.")})
    return name


@transaction.atomic
def create_category(*, organization: Organization, actor: User | None, name: str) -> Category:
    category = Category.objects.create(organization=organization, name=_check_category_name(organization, name))
    audit.record(
        organization=organization,
        actor=actor,
        action="category.created",
        target=category,
        after={"name": category.name},
    )
    return category


@transaction.atomic
def rename_category(*, category: Category, actor: User | None, name: str) -> Category:
    before = category.name
    category.name = _check_category_name(category.organization, name, exclude=category)
    category.save(update_fields=["name", "updated_at"])
    if category.name != before:
        audit.record(
            organization=category.organization,
            actor=actor,
            action="category.renamed",
            target=category,
            before={"name": before},
            after={"name": category.name},
        )
    return category


def _clean_product(product: Product) -> None:
    """Business rules shared by creation and update. Raises ValidationError with one message per field."""
    errors: dict[str, str] = {}
    product.reference = product.reference.strip()
    product.name = product.name.strip()
    product.name_ar = product.name_ar.strip()
    if not product.reference:
        errors["reference"] = _("La référence est obligatoire.")
    elif (
        Product.objects.for_organization(product.organization)
        .filter(reference__iexact=product.reference)
        .exclude(pk=product.pk)
        .exists()
    ):
        errors["reference"] = _("Un autre produit porte déjà cette référence.")
    if not product.name:
        errors["name"] = _("Le nom est obligatoire.")
    if product.category.organization_id != product.organization_id:
        errors["category"] = _("Catégorie inconnue.")
    if product.illustration not in Illustration.values:
        errors["illustration"] = _("Dessin inconnu.")
    try:
        product.min_stock = checked_quantity(product.min_stock, allow_zero=True)
    except (ValueError, TypeError) as error:
        errors["min_stock"] = str(error)
    low, high = product.storage_temp_min, product.storage_temp_max
    if low is not None and high is not None and low > high:
        errors["storage_temp_max"] = _("La température maximale doit être supérieure ou égale à la minimale.")
    if errors:
        raise ValidationError(errors)


@transaction.atomic
def create_product(
    *, organization: Organization, actor: User | None, sale_price: Number, **fields: Unpack[ProductFields]
) -> Product:
    """A new product, with its first sale price in force from now."""
    product = Product(organization=organization, base_unit=selectors.base_unit(), **fields)
    _clean_product(product)
    product.save()
    first_price = _add_price(product=product, actor=actor, price=sale_price, valid_from=timezone.now())
    audit.record(
        organization=organization,
        actor=actor,
        action="product.created",
        target=product,
        after={**_snapshot(product), "sale_price": first_price.price},
    )
    return product


@transaction.atomic
def update_product(*, product: Product, actor: User | None, **fields: Unpack[ProductFields]) -> Product:
    """Change the description of a product. Its price changes with `set_sale_price`, never here."""
    product = Product.objects.select_for_update().select_related("category").get(pk=product.pk)
    before = _snapshot(product)
    for field, value in fields.items():
        setattr(product, field, value)
    _clean_product(product)
    product.save()
    after = _snapshot(product)
    changed = [field for field in after if after[field] != before[field]]
    if changed:
        audit.record(
            organization=product.organization,
            actor=actor,
            action="product.updated",
            target=product,
            before={field: before[field] for field in changed},
            after={field: after[field] for field in changed},
        )
    return product


@transaction.atomic
def set_product_active(*, product: Product, actor: User | None, is_active: bool) -> Product:
    """Archive a product (it keeps its history but is no longer bought or sold), or bring it back."""
    product = Product.objects.select_for_update().get(pk=product.pk)
    if product.is_active != is_active:
        product.is_active = is_active
        product.save(update_fields=["is_active", "updated_at"])
        action = "product.restored" if is_active else "product.archived"
        audit.record(organization=product.organization, actor=actor, action=action, target=product)
    return product


def _add_price(*, product: Product, actor: User | None, price: Number, valid_from: dt.datetime) -> ProductPrice:
    try:
        amount = money(price)
    except (TypeError, ArithmeticError):
        raise ValidationError({"price": _("Prix invalide.")}) from None
    if amount <= 0:
        raise ValidationError({"price": _("Le prix doit être supérieur à zéro.")})
    if product.prices.filter(valid_from=valid_from).exists():
        raise ValidationError({"valid_from": _("Un prix commence déjà à ce moment.")})
    created = ProductPrice.objects.create(
        organization=product.organization, product=product, price=amount, valid_from=valid_from, created_by=actor
    )
    if selectors.is_below_minimum(product, amount):
        # A warning on the screen, never a block; the audit keeps the trace (D-049).
        audit.record(
            organization=product.organization,
            actor=actor,
            action="product.price_below_minimum",
            target=product,
            after={"price": amount, "min_price": product.min_price, "valid_from": valid_from},
        )
    return created


@transaction.atomic
def set_sale_price(
    *, product: Product, actor: User | None, price: Number, valid_from: dt.datetime | None = None
) -> ProductPrice:
    """A new sale price from now, or from a later moment. Past prices are history and never change (D-020)."""
    now = timezone.now()
    if valid_from is None:
        valid_from = now
    elif valid_from < now:
        raise ValidationError({"valid_from": _("Un nouveau prix ne peut pas commencer dans le passé.")})
    # Locks the product so two price changes at the same moment cannot interleave.
    product = Product.objects.select_for_update().get(pk=product.pk)
    if not product.is_active:
        raise ValidationError({"price": _("Ce produit est archivé.")})
    previous = selectors.price_at(product, valid_from)
    product_price = _add_price(product=product, actor=actor, price=price, valid_from=valid_from)
    audit.record(
        organization=product.organization,
        actor=actor,
        action="product.price_set",
        target=product,
        before={"price": previous.price if previous else None},
        after={"price": product_price.price, "valid_from": valid_from},
    )
    return product_price


def _delete_file_after_commit(product: Product, name: str) -> None:
    storage = product.photo.storage
    transaction.on_commit(lambda: storage.delete(name))


@transaction.atomic
def set_product_photo(*, product: Product, actor: User | None, upload: UploadedFile[bytes]) -> Product:
    content = reencoded_photo(upload)
    product = Product.objects.select_for_update().get(pk=product.pk)
    old_name = product.photo.name or ""
    product.photo.save("photo.webp", content, save=False)
    try:
        product.save(update_fields=["photo", "updated_at"])
        audit.record(organization=product.organization, actor=actor, action="product.photo_set", target=product)
    except BaseException:
        # The file is written before the row: never leave it behind when the change is rolled back.
        if product.photo.name:
            product.photo.storage.delete(product.photo.name)
        raise
    if old_name:
        _delete_file_after_commit(product, old_name)
    return product


@transaction.atomic
def remove_product_photo(*, product: Product, actor: User | None) -> Product:
    product = Product.objects.select_for_update().get(pk=product.pk)
    old_name = product.photo.name or ""
    if old_name:
        product.photo.name = ""
        product.save(update_fields=["photo", "updated_at"])
        audit.record(organization=product.organization, actor=actor, action="product.photo_removed", target=product)
        _delete_file_after_commit(product, old_name)
    return product


class PriceChange(TypedDict, total=False):
    """One row of the "Prix du jour" screen. `min_price` is left out to keep it, null to remove it."""

    product: Product
    price: Number
    min_price: Number | None


@dataclass(frozen=True)
class PriceUpdateResult:
    changed: list[ProductPrice]
    # Products whose new price is below their minimum price: shown as a warning.
    below_minimum: list[Product]


def _check_min_price(value: Number | None) -> Decimal | None:
    if value is None:
        return None
    try:
        amount = money(value)
    except (TypeError, ArithmeticError):
        raise ValidationError({"min_price": _("Prix minimum invalide.")}) from None
    if amount <= 0:
        raise ValidationError({"min_price": _("Le prix minimum doit être supérieur à zéro.")})
    return amount


@transaction.atomic
def set_sale_prices(*, organization: Organization, actor: User | None, changes: list[PriceChange]) -> PriceUpdateResult:
    """The "Prix du jour" save: new sale prices from now for many products, all or nothing (D-049).

    A product whose price equals the one in force is left alone, so saving the prefilled screen creates no
    noise. Prices below the product's minimum are accepted and returned as warnings. Any error (unknown or
    archived product, bad amount) cancels the whole save.
    """
    now = timezone.now()
    ids = [change["product"].pk for change in changes]
    if len(set(ids)) != len(ids):
        raise ValidationError({"items": _("Un produit apparaît plusieurs fois.")})
    # Locked in a fixed order so two saves at the same time cannot deadlock.
    locked = {
        product.pk: product
        for product in Product.objects.for_organization(organization)
        .select_for_update()
        .filter(pk__in=ids)
        .order_by("pk")
    }
    changed: list[ProductPrice] = []
    below: list[Product] = []
    for change in changes:
        product = locked.get(change["product"].pk)
        if product is None:
            raise ValidationError({"items": _("Produit inconnu.")})
        if not product.is_active:
            raise ValidationError({"items": _("Le produit « %(name)s » est archivé.") % {"name": product.name}})
        if "min_price" in change:
            minimum: Decimal | None = _check_min_price(change["min_price"])
            if minimum != product.min_price:
                before = product.min_price
                product.min_price = minimum
                product.save(update_fields=["min_price", "updated_at"])
                audit.record(
                    organization=organization,
                    actor=actor,
                    action="product.min_price_set",
                    target=product,
                    before={"min_price": before},
                    after={"min_price": minimum},
                )
        if "price" not in change:
            continue
        try:
            amount = money(change["price"])
        except (TypeError, ArithmeticError):
            raise ValidationError({"price": _("Prix invalide.")}) from None
        current = selectors.price_at(product, now)
        if current is None or current.price != amount:
            created = _add_price(product=product, actor=actor, price=amount, valid_from=now)
            audit.record(
                organization=organization,
                actor=actor,
                action="product.price_set",
                target=product,
                before={"price": current.price if current else None},
                after={"price": created.price, "valid_from": now},
            )
            changed.append(created)
        if selectors.is_below_minimum(product, amount):
            below.append(product)
    return PriceUpdateResult(changed=changed, below_minimum=below)


class PriceListItemInput(TypedDict):
    product: Product
    price: Number


def _replace_items(price_list: PriceList, items: list[PriceListItemInput]) -> dict[str, Decimal]:
    organization = price_list.organization
    seen: set[int] = set()
    rows: list[PriceListItem] = []
    for item in items:
        product = item["product"]
        if product.organization_id != organization.pk:
            raise ValidationError({"items": _("Produit inconnu.")})
        if product.pk in seen:
            raise ValidationError({"items": _("Un produit apparaît plusieurs fois.")})
        seen.add(product.pk)
        try:
            amount = money(item["price"])
        except (TypeError, ArithmeticError):
            raise ValidationError({"items": _("Prix invalide.")}) from None
        if amount <= 0:
            raise ValidationError({"items": _("Le prix doit être supérieur à zéro.")})
        rows.append(PriceListItem(organization=organization, price_list=price_list, product=product, price=amount))
    price_list.items.all().delete()
    PriceListItem.objects.bulk_create(rows)
    return {str(row.product_id): row.price for row in rows}


def _clean_price_list(
    organization: Organization, name: str, customer_id: int | None, *, exclude: PriceList | None
) -> str:
    name = name.strip()
    if not name:
        raise ValidationError({"name": _("Le nom est obligatoire.")})
    others = PriceList.objects.for_organization(organization)
    if exclude is not None:
        others = others.exclude(pk=exclude.pk)
    if others.filter(name__iexact=name).exists():
        raise ValidationError({"name": _("Une liste de prix porte déjà ce nom.")})
    if customer_id is not None:
        try:
            partner_selectors.customer_of(organization, customer_id)
        except ObjectDoesNotExist:
            raise ValidationError({"customer": _("Client inconnu.")}) from None
        if others.filter(customer_id=customer_id).exists():
            raise ValidationError({"customer": _("Ce client a déjà une liste de prix.")})
    return name


@transaction.atomic
def create_price_list(
    *,
    organization: Organization,
    actor: User | None,
    name: str,
    customer_id: int | None = None,
    items: list[PriceListItemInput],
) -> PriceList:
    name = _clean_price_list(organization, name, customer_id, exclude=None)
    price_list = PriceList.objects.create(organization=organization, name=name, customer_id=customer_id)
    prices = _replace_items(price_list, items)
    audit.record(
        organization=organization,
        actor=actor,
        action="price_list.created",
        target=price_list,
        after={"name": name, "customer": customer_id, "items": prices},
    )
    return price_list


@transaction.atomic
def update_price_list(
    *,
    price_list: PriceList,
    actor: User | None,
    name: str,
    customer_id: int | None,
    is_active: bool,
    items: list[PriceListItemInput],
) -> PriceList:
    """Rename, relink, archive or replace the items of a list. Every change is audited."""
    price_list = PriceList.objects.select_for_update().get(pk=price_list.pk)
    organization = price_list.organization
    before = {
        "name": price_list.name,
        "customer": price_list.customer_id,
        "is_active": price_list.is_active,
        "items": {str(item.product_id): item.price for item in price_list.items.all()},
    }
    price_list.name = _clean_price_list(organization, name, customer_id, exclude=price_list)
    price_list.customer_id = customer_id
    price_list.is_active = is_active
    price_list.save()
    prices = _replace_items(price_list, items)
    after = {"name": price_list.name, "customer": customer_id, "is_active": is_active, "items": prices}
    if after != before:
        audit.record(
            organization=organization,
            actor=actor,
            action="price_list.updated",
            target=price_list,
            before=before,
            after=after,
        )
    return price_list
