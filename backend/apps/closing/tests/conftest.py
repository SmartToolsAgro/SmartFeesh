"""A real lot for the closing tests: received, sold in pieces, partly spoiled, with costs (D-061)."""

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.tests.factories import ProductFactory
from apps.core.models import Role
from apps.core.tests.factories import MembershipFactory
from apps.expenses import selectors as expenses
from apps.expenses import services as expense_services
from apps.hr import services as hr
from apps.hr.tests.factories import EmployeeFactory
from apps.inventory import services as inventory
from apps.inventory.models import LossReason, MovementKind
from apps.inventory.tests.factories import BatchFactory, StockLocationFactory
from apps.partners.tests.factories import CustomerFactory, SupplierFactory
from apps.partnerships import services as partnerships
from apps.sales import services as sales


@pytest.fixture
def owner(db):
    return MembershipFactory.create(role=Role.OWNER)


@pytest.fixture
def organization(owner):
    return owner.organization


@pytest.fixture
def actor(owner):
    return owner.user


def member(organization, role):
    return MembershipFactory.create(organization=organization, role=role)


def client_for(membership):
    client = APIClient()
    client.force_authenticate(membership.user)
    return client


@pytest.fixture
def api(owner):
    return client_for(owner)


@pytest.fixture
def cold_room(organization):
    return StockLocationFactory.create(organization=organization, name="Chambre froide 1", counter_sales=True)


@pytest.fixture
def partner(organization):
    return SupplierFactory.create(organization=organization, name="Pêcherie Kerkennah")


def days_ago(days: int) -> dt.date:
    return timezone.localdate() - dt.timedelta(days=days)


def receive(organization, location, kg: str, *, cost: str = "20.000", name: str = "Dorade", supplier=None):
    product = ProductFactory.create(organization=organization, name=name)
    fields: dict[str, Any] = {"supplier": supplier} if supplier is not None else {}
    batch = BatchFactory.create(
        organization=organization, product=product, unit_cost=Decimal(cost), received_on=days_ago(3), **fields
    )
    inventory.post_movement(
        organization=organization, actor=None, kind=MovementKind.RECEIPT, batch=batch, quantity=kg, to_location=location
    )
    return batch


def sell(organization, actor, location, batch, kg: str, price: str, *, paid: bool = True):
    customer = CustomerFactory.create(organization=organization)
    return sales.create_sale(
        organization=organization,
        actor=actor,
        customer=customer,
        location=location,
        lines=[{"product": batch.product, "quantity": kg, "unit_price": price}],
        payment={"paid_in_full": True, "payment_method": "cash"} if paid else {},
        confirm=True,
    )


def lose(organization, actor, location, batch, kg: str):
    return inventory.record_loss(
        organization=organization,
        actor=actor,
        location=location,
        product=batch.product,
        quantity=kg,
        reason=LossReason.SPOILED,
        lost_on=timezone.localdate(),
        may_approve=True,
    )


def cost(organization, actor, batch, code: str, amount: str, *, approve: bool = True):
    return expense_services.create_expense(
        organization=organization,
        actor=actor,
        spent_on=timezone.localdate(),
        category=expenses.category_by_code(organization, code),
        amount=amount,
        batch=batch,
        approve=approve,
    )


def employee_day(organization, actor, batch, days: str, salary: str = "2600.000"):
    employee = EmployeeFactory.create(organization=organization, monthly_salary=Decimal(salary))
    return hr.add_lot_work_day(
        organization=organization, actor=actor, employee=employee, work_date=days_ago(1), days=days, batch=batch
    )


def partnership(organization, actor, batch, partner, *, capital="1000.000", profit="40", loss="25"):
    return partnerships.create_partnership(
        organization=organization,
        actor=actor,
        batch=batch,
        partner=partner,
        owner_capital="1000.000",
        partner_capital=capital,
        profit_rate=profit,
        loss_rate=loss,
    )


@pytest.fixture
def finished_lot(organization, actor, cold_room, partner):
    """The reference lot of test_engine, built for real: 100 kg at 20.000 in partnership (1 000.000 of
    capital, 40 % / 25 %), sold 40 kg at 32.500, 35 kg at 30.000 and 20 kg at 28.750, 5 kg spoiled,
    transport 120.000 and handling 40.000 typed on it, an employee half a day at 2 600.000 a month (50.000)."""
    batch = receive(organization, cold_room, "100.000")
    partnership(organization, actor, batch, partner)
    sell(organization, actor, cold_room, batch, "40.000", "32.500")
    sell(organization, actor, cold_room, batch, "35.000", "30.000")
    sell(organization, actor, cold_room, batch, "20.000", "28.750")
    lose(organization, actor, cold_room, batch, "5.000")
    cost(organization, actor, batch, "transport", "120.000")
    cost(organization, actor, batch, "handling", "40.000")
    employee_day(organization, actor, batch, "0.50")
    return batch
