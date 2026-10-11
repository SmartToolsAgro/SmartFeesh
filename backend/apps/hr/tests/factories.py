from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from apps.core.tests.factories import OrganizationFactory
from apps.hr.models import Employee


class EmployeeFactory(DjangoModelFactory[Employee]):
    class Meta:
        model = Employee

    organization = factory.SubFactory(OrganizationFactory)
    reference = factory.Sequence(lambda n: f"E-{n + 1:03d}")
    name = factory.Sequence(lambda n: f"Employé {n}")
    position = "Manutentionnaire"
    monthly_salary = Decimal("1300.000")
    cnss_rate = Decimal("17.07")
