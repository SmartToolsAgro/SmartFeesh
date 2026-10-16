"""A truck load split by client leaves a draft BL for each of them (D-160)."""

import datetime as dt
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.boxes import selectors as box_selectors
from apps.boxes import services as box_services
from apps.boxes.models import BoxHolder, BoxMovementKind
from apps.catalog.tests.factories import ProductFactory, ProductPriceFactory
from apps.core.tests.factories import OrganizationFactory, UserFactory
from apps.inventory import selectors as inventory
from apps.inventory import services as inventory_services
from apps.inventory.models import LocationKind, MovementKind
from apps.inventory.tests.factories import BatchFactory, StockLocationFactory
from apps.partners.tests.factories import CustomerFactory
from apps.sales import printing, services
from apps.sales.models import Sale, SaleStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def organization():
    return OrganizationFactory.create()


@pytest.fixture
def actor():
    return UserFactory.create()


@pytest.fixture
def cold_room(organization):
    return StockLocationFactory.create(organization=organization, name="Chambre froide 1")


@pytest.fixture
def truck(organization):
    return StockLocationFactory.create(organization=organization, kind=LocationKind.TRUCK, name="Camion 1")


@pytest.fixture
def dorade(organization):
    product = ProductFactory.create(organization=organization, name="Dorade royale", reference="DO-003")
    ProductPriceFactory.create(
        product=product, price=Decimal("28.000"), valid_from=timezone.now() - dt.timedelta(days=3)
    )
    return product


@pytest.fixture
def restaurant(organization):
    return CustomerFactory.create(
        organization=organization, name="Le Corail", address="Avenue Hédi Chaker", city="Sfax"
    )


@pytest.fixture
def hotel(organization):
    return CustomerFactory.create(organization=organization, name="Hôtel Thyna", address="Route Gabès", city="Sfax")


@pytest.fixture
def stocked(organization, cold_room, dorade):
    """50 kg of dorade in the cold room and 20 boxes of each size at the company."""
    batch = BatchFactory.create(organization=organization, product=dorade, received_on=timezone.localdate())
    inventory_services.post_movement(
        organization=organization,
        actor=None,
        kind=MovementKind.RECEIPT,
        batch=batch,
        quantity=Decimal("50"),
        to_location=cold_room,
    )
    box_services.post_box_counts(
        organization=organization,
        actor=None,
        kind=BoxMovementKind.OPENING,
        counts={"small": 20, "big": 20},
        to_holder=box_services.holder_for(organization=organization, location=cold_room),
    )
    return batch


def load(organization, actor, cold_room, truck, deliveries, *, lines=(), boxes=None, validate=True):
    return inventory_services.create_transfer(
        organization=organization,
        actor=actor,
        from_location=cold_room,
        to_location=truck,
        transferred_on=timezone.localdate(),
        lines=list(lines),
        boxes=boxes,
        deliveries=deliveries,
        validate=validate,
    )


def part(customer, dorade, kg, *, address="", boxes=None):
    return {
        "customer": customer,
        "delivery_address": address,
        "lines": [{"product": dorade, "quantity": kg}],
        "boxes": boxes or {},
    }


def test_a_validated_load_leaves_a_draft_bl_for_each_client(
    organization, actor, cold_room, truck, dorade, restaurant, hotel, stocked
):
    transfer = load(
        organization,
        actor,
        cold_room,
        truck,
        [
            part(restaurant, dorade, "12.500", boxes={"small": 2, "big": 1}),
            part(hotel, dorade, "20", address="Zone industrielle Thyna", boxes={"big": 3}),
        ],
    )

    assert inventory.quantity_on_hand(organization, location_id=truck.pk) == Decimal("32.500")
    sales_by_customer = {
        sale.customer_id: sale
        for sale in Sale.objects.filter(transfer=transfer).select_related("customer")
    }
    corail = sales_by_customer[restaurant.pk]
    thyna = sales_by_customer[hotel.pk]
    assert (corail.customer, corail.status, corail.location) == (restaurant, SaleStatus.DRAFT, truck)
    assert corail.delivery_address == "Avenue Hédi Chaker, Sfax"  # the client's own, copied
    assert thyna.delivery_address == "Zone industrielle Thyna"  # typed for this BL only
    restaurant.refresh_from_db()
    assert restaurant.address == "Avenue Hédi Chaker"
    (line,) = corail.lines.all()
    assert (line.quantity, line.unit_price) == (Decimal("12.500"), Decimal("28.000"))  # the load's price of the day
    assert {box.box_type: box.count for box in corail.box_lines.all()} == {"small": 2, "big": 1}
    assert {box.box_type: box.count for box in thyna.box_lines.all()} == {"big": 3}
    # Nothing is sold yet: the truck still holds the kilos and the boxes.
    assert corail.confirmed_at is None
    assert corail.total == Decimal("350.000")


def test_the_boxes_of_every_client_go_to_the_truck_with_the_load(
    organization, actor, cold_room, truck, dorade, restaurant, hotel, stocked
):
    load(
        organization,
        actor,
        cold_room,
        truck,
        [part(restaurant, dorade, "5", boxes={"small": 2}), part(hotel, dorade, "5", boxes={"small": 3, "big": 1})],
        boxes={"big": 1},
    )

    on_truck = box_services.holder_for(organization=organization, location=truck)
    assert box_selectors.balance_of(organization, on_truck, "small") == 5
    assert box_selectors.balance_of(organization, on_truck, "big") == 2


def test_confirming_a_client_bl_takes_the_stock_and_the_boxes_off_the_truck(
    organization, actor, cold_room, truck, dorade, restaurant, stocked
):
    transfer = load(organization, actor, cold_room, truck, [part(restaurant, dorade, "10", boxes={"small": 4})])
    (sale,) = Sale.objects.filter(transfer=transfer)

    services.confirm_sale(sale=sale, actor=actor)

    assert inventory.quantity_on_hand(organization, location_id=truck.pk) == Decimal("0.000")
    holder = BoxHolder.objects.get(organization=organization, customer=restaurant)
    assert box_selectors.balance_of(organization, holder, "small") == 4
    sale.refresh_from_db()
    assert sale.number.startswith("BL-")
    assert sale.amount_due == Decimal("280.000")


def test_changing_the_lines_of_a_draft_bl_keeps_its_address_and_boxes(
    organization, actor, cold_room, truck, dorade, restaurant, stocked
):
    transfer = load(
        organization, actor, cold_room, truck, [part(restaurant, dorade, "10", address="Quai 3", boxes={"big": 2})]
    )
    (sale,) = Sale.objects.filter(transfer=transfer)

    services.update_sale(
        sale=sale,
        actor=actor,
        customer=restaurant,
        location=truck,
        lines=[{"product": dorade, "quantity": "8", "unit_price": "28.000"}],
    )
    sale.refresh_from_db()
    assert sale.delivery_address == "Quai 3"
    assert {box.box_type: box.count for box in sale.box_lines.all()} == {"big": 2}

    services.update_sale(
        sale=sale,
        actor=actor,
        customer=restaurant,
        location=truck,
        lines=[{"product": dorade, "quantity": "8", "unit_price": "28.000"}],
        delivery_address="Quai 5",
    )
    sale.refresh_from_db()
    assert sale.delivery_address == "Quai 5"
    restaurant.refresh_from_db()
    assert restaurant.address == "Avenue Hédi Chaker"


def test_the_draft_bl_prints_as_provisional_with_its_address_and_boxes(
    organization, actor, cold_room, truck, dorade, restaurant, stocked
):
    transfer = load(
        organization, actor, cold_room, truck, [part(restaurant, dorade, "10", address="Quai 3", boxes={"big": 2})]
    )
    (sale,) = Sale.objects.filter(transfer=transfer)

    printable = printing.delivery_note_printable(organization, sale.pk)

    assert printable.context["provisional"] is True
    assert printable.context["deliver_to"] == "Quai 3"
    assert printable.context["boxes"] == [("Grande caisse", 2)]


def test_an_ordinary_draft_sale_still_has_no_bl(organization, actor, truck, dorade, restaurant):
    sale = services.create_sale(
        organization=organization,
        actor=actor,
        customer=restaurant,
        location=truck,
        lines=[{"product": dorade, "quantity": "1", "unit_price": "28.000"}],
    )

    with pytest.raises(ValidationError):
        printing.delivery_note_printable(organization, sale.pk)


def test_a_client_part_that_asks_for_too_much_is_refused_on_its_own_line(
    organization, actor, cold_room, truck, dorade, restaurant, hotel, stocked
):
    with pytest.raises(ValidationError) as refused:
        load(organization, actor, cold_room, truck, [part(restaurant, dorade, "30"), part(hotel, dorade, "30")])

    assert "deliveries.1.lines.0.quantity" in refused.value.message_dict
    assert not Sale.objects.filter(organization=organization).exists()
    assert inventory.quantity_on_hand(organization, location_id=truck.pk) == Decimal("0.000")


def test_a_client_appears_once_and_only_a_load_is_split_by_client(
    organization, actor, cold_room, truck, dorade, restaurant, stocked
):
    with pytest.raises(ValidationError) as twice:
        load(organization, actor, cold_room, truck, [part(restaurant, dorade, "5"), part(restaurant, dorade, "5")])
    other_room = StockLocationFactory.create(organization=organization, name="Chambre froide 2")
    with pytest.raises(ValidationError) as not_a_load:
        load(organization, actor, cold_room, other_room, [part(restaurant, dorade, "5")])

    assert "deliveries.1.customer" in twice.value.message_dict
    assert "deliveries" in not_a_load.value.message_dict


def test_the_part_kept_on_the_truck_makes_no_bl(organization, actor, cold_room, truck, dorade, restaurant, stocked):
    transfer = load(
        organization,
        actor,
        cold_room,
        truck,
        [part(restaurant, dorade, "10")],
        lines=[{"product": dorade, "quantity": "15"}],
    )

    assert inventory.quantity_on_hand(organization, location_id=truck.pk) == Decimal("25.000")
    assert Sale.objects.filter(transfer=transfer).count() == 1
