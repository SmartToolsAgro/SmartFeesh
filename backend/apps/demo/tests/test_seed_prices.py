import pytest

from apps.catalog import selectors
from apps.core.tests.factories import OrganizationFactory
from apps.demo.catalogue import seed_catalogue
from apps.demo.customers import seed_customers
from apps.demo.prices import seed_prices

pytestmark = pytest.mark.django_db


def test_minimum_prices_and_the_hotel_list_are_created_once():
    organization = OrganizationFactory.create()
    seed_catalogue(organization=organization, actor=None)
    seed_customers(organization=organization, actor=None)

    assert seed_prices(organization=organization, actor=None) == 13  # 12 minimums + 1 list
    assert seed_prices(organization=organization, actor=None) == 0

    royale = selectors.products_of(organization).get(reference="CR-001")
    assert str(royale.min_price) == "33.600"
    assert selectors.price_lists_of(organization).get().items.count() == 3
