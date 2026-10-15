from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalog.models import Category, Product, ProductPrice
from apps.core.models import Organization, User
from apps.expenses.models import Expense
from apps.fleet.models import Truck
from apps.hr.models import Employee
from apps.inventory.models import StockLocation, StockMovement
from apps.partners.models import Customer, Supplier
from apps.sales.models import Invoice, Sale

pytestmark = pytest.mark.django_db


def _seeded(settings) -> Organization:
    settings.DEBUG = True
    call_command("seed_dev", stdout=StringIO())
    # One demo product gets an article code of the owner's list; the other stand-ins have no ART code.
    Product.objects.filter(reference="CR-001").update(reference="ART0002")
    return Organization.objects.get()


def _business_rows() -> dict[str, int]:
    return {
        "stock movements": StockMovement.objects.count(),
        "sales": Sale.objects.count(),
        "invoices": Invoice.objects.count(),
        "expenses": Expense.objects.count(),
        "customers": Customer.objects.count(),
        "suppliers": Supplier.objects.count(),
        "prices": ProductPrice.objects.count(),
    }


def test_reset_keeps_the_master_data_and_empties_the_business(settings):
    organization = _seeded(settings)
    before = _business_rows()
    assert all(count > 0 for count in before.values()), before
    locations = StockLocation.objects.count()
    trucks = Truck.objects.count()

    call_command("prepare_client_start", "--keep-employee", "Rim K.", "--apply", stdout=StringIO())

    assert _business_rows() == dict.fromkeys(before, 0)
    assert list(Product.objects.values_list("reference", flat=True)) == ["ART0002"]
    product = Product.objects.get()
    assert product.min_price is None
    assert product.min_stock == 0
    assert list(Category.objects.values_list("pk", flat=True)) == [product.category_id]
    assert list(Employee.objects.values_list("name", flat=True)) == ["Rim K."]
    assert StockLocation.objects.count() == locations
    assert Truck.objects.count() == trucks
    assert not Truck.objects.filter(driver__isnull=False).exists()
    assert Organization.objects.filter(pk=organization.pk).exists()
    assert User.objects.count() == 2
    assert not User.objects.get(username="owner").check_password("frutti-dev")


def test_dry_run_changes_nothing(settings):
    _seeded(settings)
    before = {**_business_rows(), "products": Product.objects.count(), "employees": Employee.objects.count()}
    output = StringIO()

    call_command("prepare_client_start", "--keep-employee", "Rim K.", stdout=output)

    after = {**_business_rows(), "products": Product.objects.count(), "employees": Employee.objects.count()}
    assert after == before
    assert User.objects.get(username="owner").check_password("frutti-dev")
    assert Organization.objects.get().real_data_since is None
    assert "Dry run" in output.getvalue()


def test_the_demo_seed_adds_nothing_once_the_real_data_is_in(settings):
    _seeded(settings)
    call_command("prepare_client_start", "--keep-employee", "Rim K.", "--apply", stdout=StringIO())

    call_command("seed_dev", stdout=StringIO())

    assert Organization.objects.get().real_data_since is not None
    assert Product.objects.count() == 1
    assert Employee.objects.count() == 1
    assert User.objects.count() == 2
    assert StockMovement.objects.count() == 0


def test_an_employee_name_must_match_exactly_one_employee(settings):
    _seeded(settings)

    everyone = Employee.objects.count()
    with pytest.raises(CommandError, match="matches 0 employee"):
        call_command("prepare_client_start", "--keep-employee", "Dhaker", stdout=StringIO())
    with pytest.raises(CommandError, match=f"matches {everyone} employee"):
        call_command("prepare_client_start", "--keep-employee", "", stdout=StringIO())
    assert Employee.objects.count() == everyone
