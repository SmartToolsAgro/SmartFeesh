import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.boxes import selectors
from apps.boxes import services as box_services
from apps.boxes.models import BoxHolder, BoxMovement, BoxMovementKind
from apps.catalog.tests.factories import ProductFactory, ProductPriceFactory
from apps.core.models import Role
from apps.core.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.inventory import selectors as inventory
from apps.inventory import services as inventory_services
from apps.inventory.models import LocationKind, MovementKind, StockMovement, TransferStatus
from apps.inventory.tests.factories import BatchFactory, StockLocationFactory
from apps.partners.tests.factories import CustomerFactory, SupplierFactory
from apps.purchasing import services as purchasing
from apps.purchasing.models import GoodsReceipt

pytestmark = pytest.mark.django_db


@pytest.fixture
def organization():
    return OrganizationFactory.create()


@pytest.fixture
def actor():
    return UserFactory.create()


@pytest.fixture
def supplier(organization):
    return SupplierFactory.create(organization=organization, name="Mareyeur Port de Sfax")


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


def _receive_kg(organization, product, location, kg):
    """Fish already in a location, put there directly (not through a receipt)."""
    batch = BatchFactory.create(organization=organization, product=product)
    inventory_services.post_movement(
        organization=organization, actor=None, kind=MovementKind.RECEIPT, batch=batch, quantity=kg, to_location=location
    )


def _receipt(organization, actor, supplier, location, product, *, boxes=None):
    return purchasing.create_receipt(
        organization=organization,
        actor=actor,
        supplier=supplier,
        location=location,
        received_on=timezone.localdate(),
        lines=[{"product": product, "invoiced_quantity": "30", "accepted_quantity": "30", "unit_cost": "20"}],
        boxes=boxes,
    )


def _draft(organization, actor, source, target, product, *, boxes=None, kg="12"):
    return inventory_services.create_transfer(
        organization=organization,
        actor=actor,
        from_location=source,
        to_location=target,
        transferred_on=timezone.localdate(),
        lines=[{"product": product, "quantity": kg}],
        boxes=boxes,
    )


def _holder_balance(organization, holder: BoxHolder, box_type: str = "small") -> int:
    return selectors.balance_of(organization, holder, box_type)


def _location_holder(organization, location) -> BoxHolder:
    return box_services.holder_for(organization=organization, location=location)


# ---- receipts ----


def test_a_receipt_with_boxes_posts_receive_movements_from_the_supplier(
    organization, actor, supplier, cold_room, dorade
):
    receipt = _receipt(organization, actor, supplier, cold_room, dorade, boxes={"small": 10, "big": 2})

    received = BoxMovement.objects.for_organization(organization).filter(kind=BoxMovementKind.RECEIVE)
    assert sorted((m.box_type, m.count) for m in received) == [("big", 2), ("small", 10)]
    assert all(m.source == receipt for m in received)
    assert _holder_balance(organization, _location_holder(organization, cold_room)) == 10
    assert _holder_balance(organization, _location_holder(organization, cold_room), "big") == 2
    # What we owe the supplier: the boxes it lent us.
    supplier_holder = box_services.holder_for(organization=organization, supplier=supplier)
    assert _holder_balance(organization, supplier_holder) == 10
    assert _holder_balance(organization, supplier_holder, "big") == 2


@pytest.mark.parametrize("boxes", [None, {}, {"small": 0, "big": 0}])
def test_zero_boxes_post_nothing(organization, actor, supplier, cold_room, dorade, boxes):
    _receipt(organization, actor, supplier, cold_room, dorade, boxes=boxes)

    assert not BoxMovement.objects.for_organization(organization).exists()
    assert not BoxHolder.objects.for_organization(organization).exists()


def test_a_receipt_refuses_a_negative_or_unknown_box_count_and_writes_nothing(
    organization, actor, supplier, cold_room, dorade
):
    with pytest.raises(ValidationError) as refused:
        _receipt(organization, actor, supplier, cold_room, dorade, boxes={"small": -1, "huge": 2})

    assert set(refused.value.message_dict) == {"boxes.small", "boxes.huge"}
    assert not GoodsReceipt.objects.for_organization(organization).exists()
    assert not BoxMovement.objects.for_organization(organization).exists()


def test_a_box_posting_that_fails_rolls_the_stock_back_too(
    organization, actor, supplier, cold_room, dorade, monkeypatch
):
    def refused(**_kwargs: Any) -> None:
        raise ValidationError("Refusée pour le test.")

    # Receiving boxes can hardly be refused on its own, so the refusal is forced: the stock must still roll back.
    monkeypatch.setattr(box_services, "post_box_counts", refused)

    with pytest.raises(ValidationError):
        _receipt(organization, actor, supplier, cold_room, dorade, boxes={"small": 4})

    assert not GoodsReceipt.objects.for_organization(organization).exists()
    assert not StockMovement.objects.for_organization(organization).exists()
    assert inventory.quantity_on_hand(organization, location_id=cold_room.pk) == 0


# ---- transfers ----


def test_boxes_on_a_load_move_when_the_transfer_is_validated(organization, actor, supplier, cold_room, truck, dorade):
    _receipt(organization, actor, supplier, cold_room, dorade, boxes={"big": 3})
    draft = _draft(organization, actor, cold_room, truck, dorade, boxes={"big": 3})

    assert not BoxMovement.objects.filter(kind=BoxMovementKind.LOAD).exists()  # a draft moves nothing
    inventory_services.validate_transfer(transfer=draft, actor=actor)

    (load,) = BoxMovement.objects.filter(kind=BoxMovementKind.LOAD)
    assert (load.box_type, load.count, load.source) == ("big", 3, draft)
    assert _holder_balance(organization, _location_holder(organization, truck), "big") == 3
    assert _holder_balance(organization, _location_holder(organization, cold_room), "big") == 0


def test_a_load_without_boxes_posts_no_box_movement(organization, actor, cold_room, truck, dorade):
    _receive_kg(organization, dorade, cold_room, "30")
    draft = _draft(organization, actor, cold_room, truck, dorade, boxes={})

    inventory_services.validate_transfer(transfer=draft, actor=actor)

    assert not BoxMovement.objects.for_organization(organization).exists()


def test_boxes_only_go_with_a_load(organization, actor, cold_room, truck, dorade):
    _receive_kg(organization, dorade, truck, "30")
    other_room = StockLocationFactory.create(organization=organization, name="Chambre froide 2")

    with pytest.raises(ValidationError) as back_to_room:
        _draft(organization, actor, truck, cold_room, dorade, boxes={"small": 2})
    with pytest.raises(ValidationError) as between_rooms:
        _draft(organization, actor, cold_room, other_room, dorade, boxes={"small": 2})

    assert set(back_to_room.value.message_dict) == {"boxes"}
    assert set(between_rooms.value.message_dict) == {"boxes"}
    assert not StockMovement.objects.for_organization(organization).filter(kind=MovementKind.TRANSFER).exists()


def test_a_refused_box_load_rolls_the_stock_back_too(organization, actor, cold_room, truck, dorade):
    _receive_kg(organization, dorade, cold_room, "30")  # the cold room holds no boxes at all
    draft = _draft(organization, actor, cold_room, truck, dorade, boxes={"big": 3})

    with pytest.raises(ValidationError) as refused:
        inventory_services.validate_transfer(transfer=draft, actor=actor)

    assert set(refused.value.message_dict) == {"boxes"}
    draft.refresh_from_db()
    assert draft.status == TransferStatus.DRAFT
    assert inventory.quantity_on_hand(organization, location_id=cold_room.pk) == Decimal("30.000")
    assert inventory.quantity_on_hand(organization, location_id=truck.pk) == 0
    assert not StockMovement.objects.for_organization(organization).filter(kind=MovementKind.TRANSFER).exists()
    assert not BoxMovement.objects.for_organization(organization).exists()


def test_a_draft_keeps_its_boxes_until_they_are_replaced(organization, actor, cold_room, truck, dorade):
    _receive_kg(organization, dorade, cold_room, "30")
    draft = _draft(organization, actor, cold_room, truck, dorade, boxes={"small": 5})

    draft = inventory_services.update_transfer(
        transfer=draft,
        actor=actor,
        from_location=cold_room,
        to_location=truck,
        transferred_on=timezone.localdate(),
        lines=[{"product": dorade, "quantity": "12"}],
        boxes={"big": 1},
    )

    assert sorted(draft.box_lines.values_list("box_type", "count")) == [("big", 1)]


# ---- API ----


def client_for(role, organization=None):
    membership = MembershipFactory.create(role=role, organization=organization or OrganizationFactory.create())
    client = APIClient()
    client.force_authenticate(membership.user)
    return client, membership


def test_the_owner_reads_balances_and_history_by_holder(organization, actor, supplier, cold_room, truck, dorade):
    client, _ = client_for(Role.OWNER, organization)
    _receipt(organization, actor, supplier, cold_room, dorade, boxes={"small": 10})
    draft = _draft(organization, actor, cold_room, truck, dorade, boxes={"small": 4})
    inventory_services.validate_transfer(transfer=draft, actor=actor)

    balances = client.get(reverse("box-balances")).json()
    by_holder = {(row["holder_kind"], row["holder_name"]): row["count"] for row in balances}
    assert by_holder == {
        ("location", "Chambre froide 1"): 6,
        ("location", "Camion 1"): 4,
        ("supplier", "Mareyeur Port de Sfax"): 10,
    }

    history = client.get(reverse("box-movements"), {"holder": _location_holder(organization, cold_room).pk}).json()
    assert [(row["kind"], row["count"]) for row in history["results"]] == [("load", 4), ("receive", 10)]
    assert (history["results"][0]["from_holder_name"], history["results"][0]["to_holder_name"]) == (
        "Chambre froide 1",
        "Camion 1",
    )
    assert client.get(reverse("box-movements"), {"box_type": "big"}).json()["count"] == 0


def test_a_transfer_api_call_carries_its_boxes(organization, actor, supplier, cold_room, truck, dorade):
    client, _ = client_for(Role.OWNER, organization)
    _receive_kg(organization, dorade, cold_room, "30")
    _receipt(organization, actor, supplier, cold_room, dorade, boxes={"small": 6})

    created = client.post(
        reverse("transfer-list"),
        {
            "from_location": cold_room.pk,
            "to_location": truck.pk,
            "transferred_on": timezone.localdate().isoformat(),
            "lines": [{"product": dorade.pk, "quantity": "12"}],
            "boxes": {"small": 6},
            "validate_now": True,
        },
        format="json",
    )

    assert created.status_code == 201, created.json()
    assert _holder_balance(organization, _location_holder(organization, truck)) == 6
    assert _holder_balance(organization, _location_holder(organization, cold_room)) == 0


def test_a_draft_load_shows_its_boxes_and_saving_it_back_keeps_them(organization, actor, cold_room, truck, dorade):
    client, _ = client_for(Role.OWNER, organization)
    draft = _draft(organization, actor, cold_room, truck, dorade, boxes={"small": 4})
    url = reverse("transfer-detail", args=[draft.pk])

    shown = client.get(url).json()
    assert shown["boxes"] == {"small": 4}
    no_boxes = _draft(organization, actor, cold_room, truck, dorade)
    assert client.get(reverse("transfer-detail", args=[no_boxes.pk])).json()["boxes"] == {}

    # The form reloads the boxes it shows and saves them back: a draft keeps them (saving replaces them).
    body = {
        "from_location": cold_room.pk,
        "to_location": truck.pk,
        "transferred_on": timezone.localdate().isoformat(),
        "lines": [{"product": dorade.pk, "quantity": "12"}],
        "boxes": shown["boxes"],
    }
    assert client.put(url, body, format="json").status_code == 200
    assert client.get(url).json()["boxes"] == {"small": 4}


@pytest.mark.parametrize(
    ("role", "status"),
    [(Role.OWNER, 200), (Role.MANAGER, 200), (Role.ACCOUNTANT, 200), (Role.DRIVER, 403)],
)
@pytest.mark.parametrize("name", ["box-balances", "box-movements"])
def test_only_the_office_reads_boxes(role, status, name):
    client, _ = client_for(role)

    assert client.get(reverse(name)).status_code == status


def test_anonymous_callers_get_401():
    assert APIClient().get(reverse("box-balances")).status_code == 401


def test_another_organization_boxes_are_invisible(organization, actor, supplier, cold_room, dorade):
    _receipt(organization, actor, supplier, cold_room, dorade, boxes={"small": 10})
    other, _ = client_for(Role.OWNER)

    assert other.get(reverse("box-balances")).json() == []
    assert other.get(reverse("box-movements")).json()["count"] == 0


def test_a_holder_of_another_organization_is_not_found(organization, actor, supplier, cold_room, dorade):
    _receipt(organization, actor, supplier, cold_room, dorade, boxes={"small": 10})
    other, other_owner = client_for(Role.OWNER)
    foreign_holder = box_services.holder_for(
        organization=other_owner.organization, customer=CustomerFactory.create(organization=other_owner.organization)
    )

    response = other.get(reverse("box-movements"), {"holder": _location_holder(organization, cold_room).pk})
    assert response.status_code == 404
    assert other.get(reverse("box-movements"), {"holder": foreign_holder.pk}).json()["count"] == 0
    assert BoxMovement.objects.for_organization(organization).count() == 1
