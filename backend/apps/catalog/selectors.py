"""Reusable read queries and unit helpers of the catalogue."""

import datetime as dt
from decimal import Decimal
from typing import Literal

from django.db.models import OuterRef, Q, QuerySet, Subquery
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core.models import Organization
from apps.core.money import Number, quantity

from .models import KILOGRAM, Category, Product, ProductPrice, Unit

type ProductStatus = Literal["active", "archived", "all"]


def base_unit() -> Unit:
    """The unit every quantity is stored in. Always the kilogram for now (Q10)."""
    return Unit.objects.get(code=KILOGRAM)


def to_base_quantity(value: Number, unit: Unit) -> Decimal:
    """A quantity expressed in `unit`, converted to kg and rounded to grams, ready to be stored.

    Call it wherever a quantity enters the system, so that adding box or piece units later changes
    only this function. No conversion exists yet, so any unit other than kg is refused.
    """
    if unit.code != KILOGRAM:
        raise ValueError(
            _("Aucune conversion de « %(unit)s » vers %(base)s n'est définie.") % {"unit": unit.code, "base": KILOGRAM}
        )
    return quantity(value)


def categories_of(organization: Organization) -> QuerySet[Category]:
    return Category.objects.for_organization(organization).order_by("name")


def _prices_in_force(at: dt.datetime) -> QuerySet[ProductPrice]:
    return ProductPrice.objects.filter(product=OuterRef("pk"), valid_from__lte=at).order_by("-valid_from", "-id")


def products_of(
    organization: Organization,
    *,
    search: str = "",
    category_id: int | None = None,
    status: ProductStatus = "active",
    at: dt.datetime | None = None,
) -> QuerySet[Product]:
    """Products of one organization, each with `current_price` and `current_price_from` at `at` (now)."""
    at = at or timezone.now()
    in_force = _prices_in_force(at)
    products = (
        Product.objects.for_organization(organization)
        .select_related("category", "base_unit")
        .annotate(
            current_price=Subquery(in_force.values("price")[:1]),
            current_price_from=Subquery(in_force.values("valid_from")[:1]),
        )
        .order_by("name", "id")
    )
    if status == "active":
        products = products.filter(is_active=True)
    elif status == "archived":
        products = products.filter(is_active=False)
    if category_id is not None:
        products = products.filter(category_id=category_id)
    if search := search.strip():
        products = products.filter(
            Q(name__icontains=search) | Q(name_ar__icontains=search) | Q(reference__icontains=search)
        )
    return products


def product_of(organization: Organization, product_id: int) -> Product:
    """One product with its current price. Raises Product.DoesNotExist outside the organization."""
    return products_of(organization, status="all").get(pk=product_id)


def price_at(product: Product, at: dt.datetime) -> ProductPrice | None:
    """The sale price in force at a moment: the latest one at or before it."""
    return product.prices.filter(valid_from__lte=at).order_by("-valid_from", "-id").first()


def prices_of(product: Product) -> QuerySet[ProductPrice]:
    """Every price of a product, newest first, including prices planned for later."""
    return product.prices.select_related("created_by").order_by("-valid_from", "-id")
