"""Reusable read queries and unit helpers of the catalogue."""

import datetime as dt
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from django.db.models import OuterRef, Q, QuerySet, Subquery
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core.models import Organization
from apps.core.money import MILLIME, Number, money, quantity
from apps.inventory import selectors as inventory_selectors

from .models import KILOGRAM, Category, PriceList, PriceListItem, Product, ProductPrice, Unit

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


@dataclass(frozen=True)
class PriceInForce:
    """What one kg of a product costs a customer at a moment, and where that price comes from."""

    price: Decimal
    source: Literal["price_list", "daily"]
    price_list: PriceList | None = None


def price_in_force(product: Product, at: dt.datetime, *, customer_id: int | None = None) -> PriceInForce | None:
    """The price to charge for a product at a moment (D-049).

    The customer's own price list wins when it is active and holds the product; otherwise the product's
    daily price in force (D-030). None when the product has no price yet. Sales snapshot the answer on their
    line (P2-T04); loads read the daily price (D-044).
    """
    if customer_id is not None:
        item = (
            PriceListItem.objects.filter(
                organization_id=product.organization_id,
                product=product,
                price_list__customer_id=customer_id,
                price_list__is_active=True,
            )
            .select_related("price_list")
            .first()
        )
        if item is not None:
            return PriceInForce(price=item.price, source="price_list", price_list=item.price_list)
    daily = price_at(product, at)
    return PriceInForce(price=daily.price, source="daily") if daily else None


def current_price_of(product: Product) -> Decimal | None:
    """The price in force now of a product read through `products_of` (annotated), else None."""
    price: Decimal | None = getattr(product, "current_price", None)
    return price


def is_below_minimum(product: Product, price: Decimal) -> bool:
    return product.min_price is not None and price < product.min_price


def price_lists_of(
    organization: Organization,
    *,
    customer_id: int | None = None,
    status: Literal["active", "archived", "all"] = "active",
) -> QuerySet[PriceList]:
    lists = PriceList.objects.for_organization(organization).prefetch_related("items__product").order_by("name", "id")
    if status == "active":
        lists = lists.filter(is_active=True)
    elif status == "archived":
        lists = lists.filter(is_active=False)
    if customer_id is not None:
        lists = lists.filter(customer_id=customer_id)
    return lists


def price_list_of(organization: Organization, price_list_id: int) -> PriceList:
    """One price list with its items. Raises PriceList.DoesNotExist outside the organization."""
    return price_lists_of(organization, status="all").get(pk=price_list_id)


@dataclass
class PriceBoardRow:
    product: Product
    price: Decimal | None
    price_from: dt.datetime | None
    stock: Decimal
    last_cost: Decimal | None
    average_cost: Decimal | None
    margin: Decimal | None
    margin_percent: Decimal | None
    todays_prices: list[ProductPrice] = field(default_factory=list)

    @property
    def min_price(self) -> Decimal | None:
        return self.product.min_price

    @property
    def below_minimum(self) -> bool:
        return self.price is not None and is_below_minimum(self.product, self.price)


def margin_of(price: Decimal | None, cost: Decimal | None) -> tuple[Decimal | None, Decimal | None]:
    """Margin in DT per kg and as a percentage of the price (rounded to 0.1 %)."""
    if price is None or cost is None:
        return None, None
    margin = money(price - cost)
    percent = (margin * 100 / price).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if price else None
    return margin, percent


def price_board(organization: Organization, *, at: dt.datetime | None = None) -> list[PriceBoardRow]:
    """Every active product with its price now, the cost of what is in stock and the margin (P2-T02).

    Costs come from inventory's stock on hand, all locations together: the last cost is the one of the most
    recently received batch still in stock, the average is weighted by kilos in stock. The margin is taken
    against the average cost. `todays_prices` lists the prices that started today, oldest first, so the
    screen shows who changed the price and when.
    """
    at = at or timezone.now()
    day = timezone.localtime(at).date()
    start = timezone.make_aware(dt.datetime.combine(day, dt.time.min))
    end = start + dt.timedelta(days=1)

    stock: dict[int, Decimal] = {}
    value: dict[int, Decimal] = {}
    latest: dict[int, tuple[tuple[dt.date, int], Decimal]] = {}
    for row in inventory_selectors.on_hand_of(organization):
        product_id = row.batch.product_id
        stock[product_id] = stock.get(product_id, Decimal(0)) + row.quantity
        value[product_id] = value.get(product_id, Decimal(0)) + row.quantity * row.batch.unit_cost
        key = (row.batch.received_on, row.batch_id)
        if product_id not in latest or key > latest[product_id][0]:
            latest[product_id] = (key, row.batch.unit_cost)

    todays: dict[int, list[ProductPrice]] = {}
    for item in (
        ProductPrice.objects.for_organization(organization)
        .filter(valid_from__gte=start, valid_from__lt=end)
        .select_related("created_by")
        .order_by("valid_from", "id")
    ):
        todays.setdefault(item.product_id, []).append(item)

    rows = []
    for product in products_of(organization, at=at):
        kilos = stock.get(product.pk, Decimal(0))
        average = (value[product.pk] / kilos).quantize(MILLIME, rounding=ROUND_HALF_UP) if kilos > 0 else None
        last = latest[product.pk][1] if product.pk in latest else None
        current: Decimal | None = getattr(product, "current_price", None)
        margin, percent = margin_of(current, average)
        rows.append(
            PriceBoardRow(
                product=product,
                price=current,
                price_from=getattr(product, "current_price_from", None),
                stock=quantity(kilos),
                last_cost=last,
                average_cost=average,
                margin=margin,
                margin_percent=percent,
                todays_prices=todays.get(product.pk, []),
            )
        )
    return rows
