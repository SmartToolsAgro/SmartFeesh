from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from apps.core.tests.factories import OrganizationFactory
from apps.partners.models import Customer, CustomerContact, CustomerKind, Supplier, SupplierContact


class SupplierFactory(DjangoModelFactory[Supplier]):
    class Meta:
        model = Supplier

    organization = factory.SubFactory(OrganizationFactory)
    reference = factory.Sequence(lambda n: f"F-{n + 1:03d}")
    name = factory.Sequence(lambda n: f"Fournisseur {n}")


class SupplierContactFactory(DjangoModelFactory[SupplierContact]):
    class Meta:
        model = SupplierContact

    supplier = factory.SubFactory(SupplierFactory)
    organization = factory.SelfAttribute("supplier.organization")
    name = factory.Sequence(lambda n: f"Contact {n}")


class CustomerFactory(DjangoModelFactory[Customer]):
    class Meta:
        model = Customer

    organization = factory.SubFactory(OrganizationFactory)
    reference = factory.Sequence(lambda n: f"C-{n + 1:03d}")
    name = factory.Sequence(lambda n: f"Client {n}")
    kind = CustomerKind.RESTAURANT
    # Enough credit that a test selling on credit is not stopped by the limit (P2-T06).
    credit_limit = Decimal("100000.000")


class CustomerContactFactory(DjangoModelFactory[CustomerContact]):
    class Meta:
        model = CustomerContact

    customer = factory.SubFactory(CustomerFactory)
    organization = factory.SelfAttribute("customer.organization")
    name = factory.Sequence(lambda n: f"Contact {n}")
