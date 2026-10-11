from decimal import Decimal

import pytest

from apps.core.tests.factories import OrganizationFactory
from apps.demo.customers import seed_customers
from apps.partners import selectors

pytestmark = pytest.mark.django_db


def test_the_demo_customers_and_the_walk_in_one_are_created_once():
    organization = OrganizationFactory.create()

    assert seed_customers(organization=organization, actor=None) == 9
    assert seed_customers(organization=organization, actor=None) == 0

    customers = selectors.customers_of(organization, status="all")
    assert customers.count() == 9
    hotel = customers.get(reference="C-002")
    assert (hotel.kind, hotel.credit_limit, hotel.payment_terms_days) == ("hotel", Decimal("5000.000"), 45)
    assert hotel.contacts.count() == 2
    walk_in = customers.get(is_walk_in=True)
    assert (walk_in.reference, walk_in.credit_limit) == ("C-009", Decimal("0"))
