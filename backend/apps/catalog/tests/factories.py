from decimal import Decimal

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.catalog.models import KILOGRAM, Category, Product, ProductPrice, Unit
from apps.core.tests.factories import OrganizationFactory


class CategoryFactory(DjangoModelFactory[Category]):
    class Meta:
        model = Category

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Catégorie {n}")


class ProductFactory(DjangoModelFactory[Product]):
    class Meta:
        model = Product

    organization = factory.SubFactory(OrganizationFactory)
    reference = factory.Sequence(lambda n: f"P-{n:03d}")
    name = factory.Sequence(lambda n: f"Produit {n}")
    category = factory.SubFactory(CategoryFactory, organization=factory.SelfAttribute("..organization"))
    base_unit = factory.LazyFunction(lambda: Unit.objects.get(code=KILOGRAM))
    min_stock = Decimal("10.000")


class ProductPriceFactory(DjangoModelFactory[ProductPrice]):
    class Meta:
        model = ProductPrice

    product = factory.SubFactory(ProductFactory)
    organization = factory.SelfAttribute("product.organization")
    price = Decimal("42.000")
    valid_from = factory.LazyFunction(timezone.now)
