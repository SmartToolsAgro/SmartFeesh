import datetime as dt
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog import selectors, services
from apps.catalog.models import PriceList, ProductPrice
from apps.core.models import AuditLog, Role
from apps.core.tests.factories import MembershipFactory, OrganizationFactory
from apps.inventory import services as inventory_services
from apps.inventory.models import MovementKind
from apps.inventory.tests.factories import BatchFactory, StockLocationFactory
from apps.partners.tests.factories import CustomerFactory

from .factories import ProductFactory, ProductPriceFactory

pytestmark = pytest.mark.django_db

D = Decimal


@pytest.fixture
def membership():
    return MembershipFactory.create(role=Role.MANAGER)


@pytest.fixture
def organization(membership):
    return membership.organization


@pytest.fixture
def user(membership):
    return membership.user


def product_with_price(organization, price="10.000", **fields):
    product = ProductFactory.create(organization=organization, **fields)
    ProductPriceFactory.create(product=product, price=D(price), valid_from=timezone.now() - dt.timedelta(days=3))
    return product


def stock(organization, product, kg, cost, *, received_on=None, location=None):
    location = location or StockLocationFactory.create(organization=organization)
    batch = BatchFactory.create(
        organization=organization,
        product=product,
        unit_cost=D(cost),
        **({"received_on": received_on} if received_on else {}),
    )
    inventory_services.post_movement(
        organization=organization,
        actor=None,
        kind=MovementKind.RECEIPT,
        batch=batch,
        quantity=D(kg),
        to_location=location,
    )
    return batch


def price_now(product):
    found = selectors.price_at(product, timezone.now())
    assert found is not None
    return found


def in_force(*args, **kwargs):
    found = selectors.price_in_force(*args, **kwargs)
    assert found is not None
    return found


def audit_actions(organization):
    return list(AuditLog.objects.for_organization(organization).values_list("action", flat=True))


# --- bulk update -------------------------------------------------------------------------------------------


def test_bulk_update_sets_prices_from_now_and_leaves_unchanged_ones(organization, user):
    a = product_with_price(organization, "10.000")
    b = product_with_price(organization, "20.000")

    result = services.set_sale_prices(
        organization=organization,
        actor=user,
        changes=[{"product": a, "price": D("11.500")}, {"product": b, "price": D("20.000")}],
    )

    assert [p.product_id for p in result.changed] == [a.pk]
    assert a.prices.count() == 2
    assert b.prices.count() == 1
    assert price_now(a).price == D("11.500")
    assert price_now(a).created_by == user
    # the old price stays as history
    assert a.prices.filter(price=D("10.000")).exists()


def test_bulk_update_is_all_or_nothing(organization, user):
    a = product_with_price(organization, "10.000")
    archived = product_with_price(organization, "5.000", is_active=False)

    with pytest.raises(ValidationError):
        services.set_sale_prices(
            organization=organization,
            actor=user,
            changes=[{"product": a, "price": D("12.000")}, {"product": archived, "price": D("6.000")}],
        )

    assert a.prices.count() == 1
    assert "product.price_set" not in audit_actions(organization)


def test_bulk_update_refuses_a_product_of_another_organization_and_duplicates(organization, user):
    other = product_with_price(OrganizationFactory.create())
    mine = product_with_price(organization)

    with pytest.raises(ValidationError):
        services.set_sale_prices(organization=organization, actor=user, changes=[{"product": other, "price": D("1")}])
    with pytest.raises(ValidationError):
        services.set_sale_prices(
            organization=organization,
            actor=user,
            changes=[{"product": mine, "price": D("1")}, {"product": mine, "price": D("2")}],
        )


def test_price_can_change_again_the_same_day_and_history_is_kept(organization, user):
    product = product_with_price(organization)
    services.set_sale_prices(organization=organization, actor=user, changes=[{"product": product, "price": D("12")}])
    services.set_sale_prices(organization=organization, actor=user, changes=[{"product": product, "price": D("13")}])

    row = next(r for r in selectors.price_board(organization) if r.product.pk == product.pk)

    assert row.price == D("13.000")
    assert [p.price for p in row.todays_prices] == [D("12.000"), D("13.000")]
    assert row.todays_prices[0].created_by == user


def test_price_below_minimum_is_accepted_warned_and_audited(organization, user):
    product = product_with_price(organization, "10.000")
    services.set_sale_prices(organization=organization, actor=user, changes=[{"product": product, "min_price": D("9")}])
    assert "product.min_price_set" in audit_actions(organization)

    result = services.set_sale_prices(
        organization=organization, actor=user, changes=[{"product": product, "price": D("8.500")}]
    )

    assert [p.pk for p in result.below_minimum] == [product.pk]
    assert price_now(product).price == D("8.500")
    entry = AuditLog.objects.for_organization(organization).get(action="product.price_below_minimum")
    assert entry.after is not None
    assert entry.after["price"] == "8.500"
    assert entry.after["min_price"] == "9.000"


def test_minimum_can_be_removed_and_must_be_positive(organization, user):
    product = product_with_price(organization)
    services.set_sale_prices(organization=organization, actor=user, changes=[{"product": product, "min_price": D("5")}])
    services.set_sale_prices(organization=organization, actor=user, changes=[{"product": product, "min_price": None}])
    product.refresh_from_db()
    assert product.min_price is None
    with pytest.raises(ValidationError):
        services.set_sale_prices(
            organization=organization, actor=user, changes=[{"product": product, "min_price": D("0")}]
        )


# --- price board -------------------------------------------------------------------------------------------


def test_board_shows_costs_of_the_stock_and_the_margin(organization):
    product = product_with_price(organization, "30.000")
    stock(organization, product, "10", "20.000", received_on=timezone.localdate() - dt.timedelta(days=2))
    stock(organization, product, "30", "24.000", received_on=timezone.localdate())
    empty = product_with_price(organization, "9.000")

    rows = {r.product.pk: r for r in selectors.price_board(organization)}

    row = rows[product.pk]
    assert row.stock == D("40.000")
    assert row.last_cost == D("24.000")
    assert row.average_cost == D("23.000")  # (10*20 + 30*24) / 40
    assert row.margin == D("7.000")
    assert row.margin_percent == D("23.3")
    assert rows[empty.pk].average_cost is None
    assert rows[empty.pk].margin is None


def test_board_ignores_other_organizations_and_archived_products(organization):
    product_with_price(OrganizationFactory.create())
    product_with_price(organization, is_active=False)
    mine = product_with_price(organization)

    assert [r.product.pk for r in selectors.price_board(organization)] == [mine.pk]


# --- price in force and price lists ------------------------------------------------------------------------


def test_price_in_force_uses_daily_price_then_customer_list(organization, user):
    product = product_with_price(organization, "10.000")
    customer = CustomerFactory.create(organization=organization)
    other = CustomerFactory.create(organization=organization)
    services.create_price_list(
        organization=organization,
        actor=user,
        name="Hôtel Marhaba",
        customer_id=customer.pk,
        items=[{"product": product, "price": D("8.500")}],
    )
    now = timezone.now()

    assert in_force(product, now).price == D("10.000")
    assert in_force(product, now).source == "daily"
    assert in_force(product, now, customer_id=other.pk).source == "daily"
    special = in_force(product, now, customer_id=customer.pk)
    assert (special.price, special.source) == (D("8.500"), "price_list")
    # the daily price changing does not move the customer's price
    services.set_sale_prices(organization=organization, actor=user, changes=[{"product": product, "price": D("11")}])
    assert in_force(product, timezone.now(), customer_id=customer.pk).price == D("8.500")
    # a past moment still reads the old daily price
    assert in_force(product, now).price == D("10.000")


def test_archived_price_list_is_not_used(organization, user):
    product = product_with_price(organization, "10.000")
    customer = CustomerFactory.create(organization=organization)
    price_list = services.create_price_list(
        organization=organization,
        actor=user,
        name="Liste",
        customer_id=customer.pk,
        items=[{"product": product, "price": D("8")}],
    )
    services.update_price_list(
        price_list=price_list,
        actor=user,
        name="Liste",
        customer_id=customer.pk,
        is_active=False,
        items=[{"product": product, "price": D("8")}],
    )

    assert in_force(product, timezone.now(), customer_id=customer.pk).source == "daily"


def test_price_list_rules(organization, user):
    product = product_with_price(organization)
    foreign_customer = CustomerFactory.create(organization=OrganizationFactory.create())
    customer = CustomerFactory.create(organization=organization)
    services.create_price_list(organization=organization, actor=user, name="Liste", customer_id=customer.pk, items=[])

    with pytest.raises(ValidationError):  # same name, any case
        services.create_price_list(organization=organization, actor=user, name="liste", items=[])
    with pytest.raises(ValidationError):  # customer of another organization
        services.create_price_list(
            organization=organization, actor=user, name="X", customer_id=foreign_customer.pk, items=[]
        )
    with pytest.raises(ValidationError):  # one list per customer
        services.create_price_list(organization=organization, actor=user, name="Y", customer_id=customer.pk, items=[])
    with pytest.raises(ValidationError):  # duplicate product
        services.create_price_list(
            organization=organization,
            actor=user,
            name="Z",
            items=[{"product": product, "price": D("1")}, {"product": product, "price": D("2")}],
        )
    assert PriceList.objects.count() == 1


def test_updating_a_price_list_replaces_items_and_audits(organization, user):
    a = product_with_price(organization)
    b = product_with_price(organization)
    price_list = services.create_price_list(
        organization=organization, actor=user, name="Liste", items=[{"product": a, "price": D("5")}]
    )

    services.update_price_list(
        price_list=price_list,
        actor=user,
        name="Liste promo",
        customer_id=None,
        is_active=True,
        items=[{"product": b, "price": D("6")}],
    )

    price_list = selectors.price_list_of(organization, price_list.pk)
    assert price_list.name == "Liste promo"
    assert [(i.product_id, i.price) for i in price_list.items.all()] == [(b.pk, D("6.000"))]
    assert {"price_list.created", "price_list.updated"} <= set(audit_actions(organization))


def test_prices_stay_append_only(organization):
    product = product_with_price(organization)
    with pytest.raises(TypeError):
        ProductPrice.objects.filter(product=product).update(price=D("1"))


# --- API ---------------------------------------------------------------------------------------------------


def client_for(membership):
    client = APIClient()
    client.force_authenticate(membership.user)
    return client


def test_board_api_set_and_read(membership, organization):
    product = product_with_price(organization, "10.000")
    stock(organization, product, "5", "6.000")
    api = client_for(membership)

    response = api.post(
        reverse("price-board"),
        {"items": [{"product": product.pk, "price": "9.000", "min_price": "9.500"}]},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["below_minimum"] == [product.pk]
    row = body["rows"][0]
    assert row["price"] == "9.000"
    assert row["min_price"] == "9.500"
    assert row["average_cost"] == "6.000"
    assert row["margin"] == "3.000"
    assert row["todays_prices"][0]["created_by"]
    assert api.get(reverse("price-board")).json()["rows"][0]["price"] == "9.000"


def test_board_api_roles(organization):
    product_with_price(organization)
    body = {"items": [{"product": 1, "price": "1.000"}]}
    for role, can_read, can_write in [
        (Role.OWNER, True, True),
        (Role.ACCOUNTANT, True, False),
        (Role.DRIVER, False, False),
    ]:
        api = client_for(MembershipFactory.create(organization=organization, role=role))
        assert (api.get(reverse("price-board")).status_code == 200) is can_read
        wrote = api.post(reverse("price-board"), body, format="json").status_code
        assert (wrote not in (401, 403)) is can_write
    assert APIClient().get(reverse("price-board")).status_code in (401, 403)


def test_board_api_unknown_product_is_a_validation_error(membership):
    response = client_for(membership).post(
        reverse("price-board"), {"items": [{"product": 999999, "price": "1.000"}]}, format="json"
    )
    assert response.status_code == 400


def test_price_list_api(membership, organization):
    product = product_with_price(organization)
    customer = CustomerFactory.create(organization=organization)
    api = client_for(membership)

    created = api.post(
        reverse("price-list-list"),
        {"name": "Hôtel", "customer": customer.pk, "items": [{"product": product.pk, "price": "7.250"}]},
        format="json",
    )
    assert created.status_code == 201
    body = created.json()
    assert body["customer"] == customer.pk
    assert body["items"] == [{"product": product.pk, "price": "7.250"}]

    url = reverse("price-list-detail", args=[body["id"]])
    updated = api.put(url, {"name": "Hôtel 2", "customer": customer.pk, "is_active": False, "items": []}, format="json")
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False
    assert api.get(reverse("price-list-list")).json() == []
    assert len(api.get(reverse("price-list-list"), {"status": "all"}).json()) == 1
    assert api.get(url).json()["name"] == "Hôtel 2"


def test_price_list_api_scoping_and_permissions(membership, organization):
    other_org = OrganizationFactory.create()
    other_list = services.create_price_list(organization=other_org, actor=None, name="Autre", items=[])
    api = client_for(membership)
    assert api.get(reverse("price-list-detail", args=[other_list.pk])).status_code == 404

    driver = client_for(MembershipFactory.create(organization=organization, role=Role.DRIVER))
    assert driver.get(reverse("price-list-list")).status_code == 200
    assert driver.post(reverse("price-list-list"), {"name": "x", "items": []}, format="json").status_code == 403
