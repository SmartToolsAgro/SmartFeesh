import factory
from factory.django import DjangoModelFactory

from apps.core.tests.factories import OrganizationFactory
from apps.inventory.models import LocationKind, StockLocation


class StockLocationFactory(DjangoModelFactory[StockLocation]):
    class Meta:
        model = StockLocation

    organization = factory.SubFactory(OrganizationFactory)
    kind = LocationKind.COLD_ROOM
    name = factory.Sequence(lambda n: f"Emplacement {n}")
