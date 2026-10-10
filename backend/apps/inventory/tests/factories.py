from decimal import Decimal

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.catalog.tests.factories import ProductFactory
from apps.core.tests.factories import OrganizationFactory
from apps.inventory.models import Batch, LocationKind, StockLocation
from apps.partners.tests.factories import SupplierFactory


class StockLocationFactory(DjangoModelFactory[StockLocation]):
    class Meta:
        model = StockLocation

    organization = factory.SubFactory(OrganizationFactory)
    kind = LocationKind.COLD_ROOM
    name = factory.Sequence(lambda n: f"Emplacement {n}")


class BatchFactory(DjangoModelFactory[Batch]):
    class Meta:
        model = Batch

    organization = factory.SubFactory(OrganizationFactory)
    number = factory.Sequence(lambda n: f"L-{n + 1:04d}")
    product = factory.SubFactory(ProductFactory, organization=factory.SelfAttribute("..organization"))
    supplier = factory.SubFactory(SupplierFactory, organization=factory.SelfAttribute("..organization"))
    received_on = factory.LazyFunction(timezone.localdate)
    unit_cost = Decimal("20.000")
