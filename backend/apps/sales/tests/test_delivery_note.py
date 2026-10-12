"""D-095: a validated sale is a delivery note numbered BL-<year>-<nnnn>, restarting every year."""

import datetime as dt
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.catalog.tests.factories import ProductFactory, ProductPriceFactory
from apps.core.models import AuditLog
from apps.core.tests.factories import OrganizationFactory, UserFactory
from apps.inventory import services as stock
from apps.inventory.models import MovementKind
from apps.inventory.tests.factories import BatchFactory, StockLocationFactory
from apps.partners.tests.factories import CustomerFactory
from apps.sales import printing, services
from apps.sales.models import SaleStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def organization():
    return OrganizationFactory.create()


@pytest.fixture
def actor():
    return UserFactory.create()


@pytest.fixture
def customer(organization):
    return CustomerFactory.create(organization=organization, name="Restaurant Le Corail")


@pytest.fixture
def counter(organization):
    return StockLocationFactory.create(organization=organization, name="Chambre froide 1", counter_sales=True)


@pytest.fixture
def crevette(organization):
    product = ProductFactory.create(organization=organization, name="Crevette Royale", reference="CR-001")
    ProductPriceFactory.create(
        product=product, price=Decimal("42.000"), valid_from=timezone.now() - dt.timedelta(days=30)
    )
    return product


def receive(organization, product, location, kg):
    batch = BatchFactory.create(organization=organization, product=product, unit_cost=Decimal("20.000"))
    stock.post_movement(
        organization=organization, actor=None, kind=MovementKind.RECEIPT, batch=batch, quantity=kg, to_location=location
    )


def sale(organization, actor, customer, location, lines):
    return services.create_sale(
        organization=organization, actor=actor, customer=customer, location=location, lines=lines
    )


def test_validating_numbers_the_sale_as_a_delivery_note(organization, actor, customer, counter, crevette):
    receive(organization, crevette, counter, "10")
    first = sale(organization, actor, customer, counter, [{"product": crevette, "quantity": "1"}])
    second = sale(organization, actor, customer, counter, [{"product": crevette, "quantity": "1"}])
    year = timezone.localdate().year
    assert first.number == "VE-0001"

    # Validated in the other order: numbers follow validation, not creation.
    assert services.confirm_sale(sale=second, actor=actor).number == f"BL-{year}-0001"
    assert services.confirm_sale(sale=first, actor=actor).number == f"BL-{year}-0002"
    audit = AuditLog.objects.filter(action="sale.confirmed", target_id=str(first.pk)).get()
    assert audit.after is not None
    assert audit.after["draft_number"] == "VE-0001"


def test_the_numbering_restarts_every_year(organization, actor, customer, counter, crevette, monkeypatch):
    receive(organization, crevette, counter, "10")
    last_year = timezone.localdate().year - 1
    monkeypatch.setattr("apps.sales.services.timezone.localdate", lambda *args: dt.date(last_year, 12, 31))
    old = services.confirm_sale(
        sale=sale(organization, actor, customer, counter, [{"product": crevette, "quantity": "1"}]), actor=actor
    )
    monkeypatch.undo()
    new = services.confirm_sale(
        sale=sale(organization, actor, customer, counter, [{"product": crevette, "quantity": "1"}]), actor=actor
    )
    assert old.number == f"BL-{last_year}-0001"
    assert new.number == f"BL-{timezone.localdate().year}-0001"


def test_a_refused_validation_leaves_no_gap_in_the_numbers(organization, actor, customer, counter, crevette):
    receive(organization, crevette, counter, "2")
    too_much = sale(organization, actor, customer, counter, [{"product": crevette, "quantity": "5"}])
    ok = sale(organization, actor, customer, counter, [{"product": crevette, "quantity": "1"}])

    with pytest.raises(ValidationError):
        services.confirm_sale(sale=too_much, actor=actor)

    too_much.refresh_from_db()
    assert (too_much.number, too_much.status) == ("VE-0001", SaleStatus.DRAFT)
    assert services.confirm_sale(sale=ok, actor=actor).number == f"BL-{timezone.localdate().year}-0001"


def test_only_a_validated_sale_has_a_delivery_note_pdf(organization, actor, customer, counter, crevette):
    receive(organization, crevette, counter, "10")
    draft = sale(organization, actor, customer, counter, [{"product": crevette, "quantity": "2"}])

    with pytest.raises(ValidationError, match="validez-la"):
        printing.delivery_note_printable(organization, draft.pk)

    confirmed = services.confirm_sale(sale=draft, actor=actor)
    printable = printing.delivery_note_printable(organization, confirmed.pk)
    assert printable.context["number"] == confirmed.number
    assert printable.context["total_kg"] == Decimal("2.000")
    assert printable.filename == f"bl-{confirmed.number.lower()}.pdf"
