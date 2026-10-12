"""The owner's dashboard (P7-T01, D-104): the month so far, profit and cash apart, and the alerts."""

import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.catalog.tests.factories import ProductFactory
from apps.closing import monthly
from apps.core.models import Role
from apps.expenses import selectors as expense_selectors
from apps.expenses import services as expense_services
from apps.inventory import services as inventory
from apps.inventory.models import MovementKind
from apps.inventory.tests.factories import BatchFactory
from apps.partners.tests.factories import CustomerFactory
from apps.sales import services as sales

from .conftest import client_for, member
from .test_month import build_month, day_of, moment

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def last_month():
    """The first day of the previous month."""
    return (timezone.localdate().replace(day=1) - dt.timedelta(days=1)).replace(day=1)


def test_only_the_owner_and_the_accountant_see_it(organization, owner):
    url = reverse("dashboard")
    assert client_for(owner).get(url).status_code == 200
    assert client_for(member(organization, Role.ACCOUNTANT)).get(url).status_code == 200
    assert client_for(member(organization, Role.MANAGER)).get(url).status_code == 403
    assert client_for(member(organization, Role.DRIVER)).get(url).status_code == 403


def test_an_empty_company_shows_zeros(owner):
    data = client_for(owner).get(reverse("dashboard")).json()
    assert data["month"] == timezone.localdate().replace(day=1).isoformat()
    for key in ("sales", "cash_collected", "receivables", "receivables_overdue", "stock_value", "net_result"):
        assert data[key] == "0.000", key
    assert data["overdue_customers"] == []
    assert (data["days_waiting"], data["expenses_waiting"]) == (0, 0)


def test_profit_and_cash_are_kept_apart(organization, owner, actor, cold_room, last_month):
    batch = build_month(organization, actor, cold_room, last_month)  # last month: 1 300.000 sold, 55 kg left
    product = batch.product
    today = timezone.localdate()
    late = CustomerFactory.create(organization=organization, name="Café Retard", credit_limit="1000")
    buyer = CustomerFactory.create(organization=organization, name="Hôtel Thyna", credit_limit="1000")
    # Last month, on credit: due the same day, so it is overdue now.
    sales.create_sale(
        organization=organization,
        actor=actor,
        customer=late,
        location=cold_room,
        lines=[{"product": product, "quantity": "5.000", "unit_price": "32.500"}],
        sold_at=moment(day_of(last_month, 8)),
        confirm=True,
    )
    # This month: 300.000 sold, 100.000 paid at the sale, then 50.000 more.
    sales.create_sale(
        organization=organization,
        actor=actor,
        customer=buyer,
        location=cold_room,
        lines=[{"product": product, "quantity": "10.000", "unit_price": "30.000"}],
        payment={"amount_paid": "100.000", "payment_method": "cash"},
        confirm=True,
    )
    sales.record_customer_payment(
        organization=organization, actor=actor, customer=buyer, amount="50.000", method="cash", received_on=today
    )
    expense_services.create_expense(
        organization=organization,
        actor=actor,
        spent_on=today,
        category=expense_selectors.category_by_code(organization, "transport"),
        amount="40.000",
        submit=True,
    )

    data = client_for(owner).get(reverse("dashboard")).json()

    report = monthly.month_report(organization, month=today.replace(day=1))
    # Profit: this month's sales and result are the month report's, not worked out again.
    assert data["sales"] == "300.000" == str(report.revenue)
    assert data["net_result"] == str(report.net_result)
    assert data["gross_margin"] == "100.000"  # 10 kg at 30.000, cost 20.000
    assert data["previous_sales"] == "1462.500"
    # Cash: 100 at the sale + 50 later; what is still owed is separate (and includes last month's sale).
    assert data["cash_collected"] == "150.000"
    assert data["receivables"] == "312.500"  # 162.500 (late) + 150.000 (buyer)
    assert data["receivables_overdue"] == "162.500"
    assert data["stock_value"] == "800.000"  # 40 kg left at 20.000
    assert data["overdue_customers"] == [{"customer_id": late.pk, "name": "Café Retard", "overdue": "162.500"}]
    assert data["overdue_customer_count"] == 1
    assert data["expenses_waiting"] == 1


def test_low_stock_and_expiring_lots_are_alerts(organization, owner, cold_room):
    today = timezone.localdate()
    low = ProductFactory.create(organization=organization, name="Crevette", min_stock=D("10.000"))
    fine = ProductFactory.create(organization=organization, name="Dorade", min_stock=D("10.000"))
    no_minimum = ProductFactory.create(organization=organization, name="Poulpe", min_stock=D("0.000"))

    def receive(product, kg, use_by=None):
        batch = BatchFactory.create(organization=organization, product=product, received_on=today, use_by=use_by)
        inventory.post_movement(
            organization=organization,
            actor=None,
            kind=MovementKind.RECEIPT,
            batch=batch,
            quantity=kg,
            to_location=cold_room,
        )
        return batch

    soon = receive(low, "4.000", use_by=today + dt.timedelta(days=2))
    receive(fine, "50.000", use_by=today + dt.timedelta(days=10))  # not close yet
    receive(no_minimum, "1.000")  # no use-by date: never expires, no minimum: never low

    data = client_for(owner).get(reverse("dashboard")).json()

    assert data["low_stock_count"] == 1
    assert data["low_stock"] == [{"product_id": low.pk, "name": "Crevette", "quantity": "4.000", "min_stock": "10.000"}]
    assert data["expiring_count"] == 1
    assert data["expiring"] == [
        {
            "batch_id": soon.pk,
            "batch_number": soon.number,
            "product_name": "Crevette",
            "use_by": (today + dt.timedelta(days=2)).isoformat(),
            "quantity": "4.000",
        }
    ]
