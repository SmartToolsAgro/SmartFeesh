"""Every write on the catalogue goes through these functions (ARCHITECTURE §3)."""

import datetime as dt
import io
from decimal import Decimal
from typing import Any, TypedDict, Unpack

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from PIL import Image, ImageOps, UnidentifiedImageError

from apps.core import audit
from apps.core.models import Organization, User
from apps.core.money import Number, checked_quantity, money

from . import selectors
from .models import Category, Illustration, Product, ProductPrice

MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_PHOTO_PIXELS = 50_000_000  # a 48-megapixel phone photo passes; anything larger is refused
PHOTO_SIDE = 1200  # stored photos fit in 1200 × 1200 px
PHOTO_FORMATS = {"JPEG", "PNG", "WEBP"}


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
    return ProductPrice.objects.create(
        organization=product.organization, product=product, price=amount, valid_from=valid_from, created_by=actor
    )


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


def _reencoded_photo(upload: UploadedFile[bytes]) -> ContentFile[bytes]:
    """The photo turned upright, shrunk and saved again as WebP.

    Saving again keeps only the pixels: the GPS position and other metadata of the phone, and anything
    hidden in the file, are dropped. It also keeps the server's disk small.
    """
    if upload.size is not None and upload.size > MAX_PHOTO_BYTES:
        raise ValidationError({"photo": _("La photo dépasse 8 Mo.")})
    try:
        with Image.open(upload) as image:
            if image.format not in PHOTO_FORMATS:
                raise ValidationError({"photo": _("Format accepté : JPEG, PNG ou WebP.")})
            if image.width * image.height > MAX_PHOTO_PIXELS:
                raise ValidationError({"photo": _("La photo est trop grande.")})
            upright = ImageOps.exif_transpose(image)
            upright = upright.convert("RGBA" if "A" in upright.getbands() else "RGB")
            upright.thumbnail((PHOTO_SIDE, PHOTO_SIDE))
            buffer = io.BytesIO()
            upright.save(buffer, format="WEBP", quality=82, method=4)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValidationError({"photo": _("Ce fichier n'est pas une image lisible.")}) from None
    return ContentFile(buffer.getvalue())


def _delete_file_after_commit(product: Product, name: str) -> None:
    storage = product.photo.storage
    transaction.on_commit(lambda: storage.delete(name))


@transaction.atomic
def set_product_photo(*, product: Product, actor: User | None, upload: UploadedFile[bytes]) -> Product:
    content = _reencoded_photo(upload)
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
