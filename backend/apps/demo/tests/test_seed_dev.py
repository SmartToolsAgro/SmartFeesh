from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalog import selectors as catalog
from apps.core.models import Membership, Organization, Role, User
from apps.core.selectors import active_membership
from apps.fleet import selectors as fleet
from apps.inventory import selectors as inventory
from apps.partners import selectors as partners

pytestmark = pytest.mark.django_db


def test_seed_creates_an_organization_its_logins_catalogue_suppliers_and_locations(settings):
    settings.DEBUG = True

    call_command("seed_dev")
    call_command("seed_dev")  # running it again changes nothing

    organization = Organization.objects.get()
    assert organization.name == "Frutti Del Mare"
    assert set(Membership.objects.values_list("user__username", "role")) == {
        ("owner", Role.OWNER),
        ("driver", Role.DRIVER),
    }
    owner = User.objects.get(username="owner")
    assert owner.check_password("frutti-dev")
    membership = active_membership(owner)
    assert membership is not None
    assert membership.organization == organization

    products = catalog.products_of(organization)
    assert products.count() == 12
    shrimp = products.get(reference="CR-001")
    assert (shrimp.name_ar, shrimp.category.name, getattr(shrimp, "current_price")) == (  # noqa: B009
        "قمرون ملكي",
        "Crustacés",
        Decimal("42.000"),
    )
    assert catalog.categories_of(organization).count() == 5

    suppliers = partners.suppliers_of(organization)
    assert list(suppliers.values_list("reference", flat=True)) == ["F-003", "F-002", "F-001", "F-004"]
    assert suppliers.get(reference="F-002").contacts.count() == 2

    assert [(location.kind, location.sells) for location in inventory.locations_of(organization)] == [
        ("cold_room", True),
        ("cold_room", True),
        ("truck", True),
        ("truck", True),
        ("truck", True),
    ]
    driver = Membership.objects.get(user__username="driver")
    truck = fleet.truck_of_driver(driver)
    assert truck is not None
    assert (truck.location.name, truck.plate) == ("Camion 1", "101 TU 2001")


def test_outside_development_the_known_password_is_refused(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError):
        call_command("seed_dev")
    with pytest.raises(CommandError):
        call_command("seed_dev", password="short")
    assert not User.objects.exists()


def test_staging_demo_accounts_get_the_password_given(settings):
    settings.DEBUG = False

    call_command("seed_dev", password="a-long-demo-password")

    driver = User.objects.get(username="driver")
    assert driver.check_password("a-long-demo-password")
    assert not driver.check_password("frutti-dev")
