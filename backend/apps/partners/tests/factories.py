import factory
from factory.django import DjangoModelFactory

from apps.core.tests.factories import OrganizationFactory
from apps.partners.models import Supplier, SupplierContact


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
