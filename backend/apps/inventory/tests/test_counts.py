import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.tests.factories import ProductFactory
from apps.core.models import Role
from apps.core.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.inventory import selectors, services
from apps.inventory.models import CountStatus, LocationKind, MovementKind, StockCount, StockMovement

from .factories import BatchFactory, StockLocationFactory
from .test_transfers import run_at_once

pytestmark = pytest.mark.django_db


@pytest.fixture
def organization():
    return OrganizationFactory.create()


@pytest.fixture
def actor():
    return UserFactory.create()


@pytest.fixture
def room(organization):
    return StockLocationFactory.create(organization=organization, name="Chambre froide 1")


def receive(organization, location, kg, *, product=None, days_ago=0):
    batch = BatchFactory.create(
        organization=organization,
        product=product or ProductFactory.create(organization=organization),
        received_on=timezone.localdate() - dt.timedelta(days=days_ago),
    )
    services.post_movement(
        organization=organization, actor=None, kind=MovementKind.RECEIPT, batch=batch, quantity=kg, to_location=location
    )
    return batch


def start(organization, actor, location, **fields):
    values: dict[str, Any] = {"counted_on": timezone.localdate()}
    values.update(fields)
    return services.start_count(organization=organization, actor=actor, location=location, **values)


def counted(count, actor, values):
    lines = {line.batch_id: line for line in count.lines.all()}
    return services.record_counted(
        count=count,
        actor=actor,
        lines=[{"line": lines[batch.pk].pk, "counted_quantity": kg} for batch, kg in values.items()],
    )


def on_hand(organization, location, batch):
    return selectors.quantity_on_hand(organization, location_id=location.pk, batch_id=batch.pk)


def test_the_sheet_lists_each_batch_with_what_the_ledger_expects(organization, actor, room):
    dorade = receive(organization, room, "30")
    loup = receive(organization, room, "12.5")
    receive(organization, StockLocationFactory.create(organization=organization), "7")  # elsewhere

    count = start(organization, actor, room, notes="Fin de mois")

    assert (count.number, count.status) == ("INV-0001", CountStatus.COUNTING)
    assert {(line.batch, line.expected_quantity, line.counted_quantity) for line in count.lines.all()} == {
        (dorade, Decimal("30.000"), None),
        (loup, Decimal("12.500"), None),
    }


def test_approval_posts_a_correction_for_each_difference(organization, actor, room):
    short = receive(organization, room, "30")
    over = receive(organization, room, "12")
    exact = receive(organization, room, "5")
    count = start(organization, actor, room)
    counted(count, actor, {short: "28.6", over: "12.4", exact: "5"})

    approved = services.approve_count(count=count, actor=actor)

    assert (approved.status, approved.approved_by) == (CountStatus.APPROVED, actor)
    corrections = StockMovement.objects.filter(kind=MovementKind.COUNT_CORRECTION).order_by("batch_id")
    assert [(m.batch, m.quantity, m.from_location, m.to_location) for m in corrections] == [
        (short, Decimal("1.400"), room, None),
        (over, Decimal("0.400"), None, room),
    ]
    assert corrections[0].reason == "Inventaire INV-0001"
    assert (on_hand(organization, room, short), on_hand(organization, room, over)) == (
        Decimal("28.600"),
        Decimal("12.400"),
    )
    assert selectors.on_hand_differences(organization) == []
    with pytest.raises(ValidationError, match="déjà validé"):
        services.approve_count(count=count, actor=actor)


def test_differences_apply_to_the_stock_that_moved_while_counting(organization, actor, room):
    batch = receive(organization, room, "30")
    truck = StockLocationFactory.create(organization=organization, kind=LocationKind.TRUCK)
    count = start(organization, actor, room)
    # Loaded after the sheet was made: the count still compares with the 30 kg of the sheet.
    services.post_movement(
        organization=organization,
        actor=None,
        kind=MovementKind.TRANSFER,
        batch=batch,
        quantity="10",
        from_location=room,
        to_location=truck,
    )
    counted(count, actor, {batch: "29"})

    services.approve_count(count=count, actor=actor)

    assert on_hand(organization, room, batch) == Decimal("19.000")


def test_every_line_must_be_counted_and_counts_are_checked(organization, actor, room):
    first = receive(organization, room, "3")
    second = receive(organization, room, "4")
    count = start(organization, actor, room)
    counted(count, actor, {first: "2"})

    with pytest.raises(ValidationError) as missing:
        services.approve_count(count=count, actor=actor)
    assert list(missing.value.message_dict) == ["lines"]
    with pytest.raises(ValidationError) as wrong:
        counted(count, actor, {first: "-1", second: "2,5"})
    assert set(wrong.value.message_dict) == {"lines.0.counted_quantity", "lines.1.counted_quantity"}


def test_a_shortage_bigger_than_what_is_left_is_refused_on_its_line(organization, actor, room):
    batch = receive(organization, room, "10")
    truck = StockLocationFactory.create(organization=organization, kind=LocationKind.TRUCK)
    count = start(organization, actor, room)
    services.post_movement(
        organization=organization,
        actor=None,
        kind=MovementKind.TRANSFER,
        batch=batch,
        quantity="9",
        from_location=room,
        to_location=truck,
    )
    counted(count, actor, {batch: "7"})  # 3 kg short of the sheet, but only 1 kg is left

    with pytest.raises(ValidationError) as refused:
        services.approve_count(count=count, actor=actor)

    assert list(refused.value.message_dict) == ["lines.0.counted_quantity"]
    assert not StockMovement.objects.filter(kind=MovementKind.COUNT_CORRECTION).exists()


def test_one_open_count_per_location_and_only_where_there_is_stock(organization, actor, room):
    receive(organization, room, "3")
    first = start(organization, actor, room)

    with pytest.raises(ValidationError, match=first.number):
        start(organization, actor, room)
    with pytest.raises(ValidationError) as empty:
        start(organization, actor, StockLocationFactory.create(organization=organization))
    assert list(empty.value.message_dict) == ["location"]
    with pytest.raises(ValidationError) as future:
        start(organization, actor, room, counted_on=timezone.localdate() + dt.timedelta(days=1))
    assert "counted_on" in future.value.message_dict

    services.cancel_count(count=first, actor=actor)
    assert start(organization, actor, room).number == "INV-0002"
    assert StockCount.objects.get(pk=first.pk).status == CountStatus.CANCELLED


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_two_counts_started_at_once_for_one_place_open_one_sheet():
    organization = OrganizationFactory.create()
    room = StockLocationFactory.create(organization=organization)
    receive(organization, room, "8")

    errors = run_at_once(2, lambda: start(organization, None, room))

    assert len(errors) == 1
    assert isinstance(errors[0], ValidationError)
    assert StockCount.objects.filter(location=room, status=CountStatus.COUNTING).count() == 1


# ---- API ----


def client_for(role, organization=None):
    membership = MembershipFactory.create(role=role, organization=organization or OrganizationFactory.create())
    client = APIClient()
    client.force_authenticate(membership.user)
    return client, membership


def test_the_manager_counts_a_cold_room_through_the_api():
    client, manager = client_for(Role.MANAGER)
    organization = manager.organization
    room = StockLocationFactory.create(organization=organization)
    batch = receive(organization, room, "20")

    started = client.post(
        reverse("count-list"), {"location": room.pk, "counted_on": timezone.localdate().isoformat()}, format="json"
    )
    assert started.status_code == 201
    body = started.json()
    (line,) = body["lines"]
    assert (body["number"], line["batch"]["number"], line["expected_quantity"], line["difference"]) == (
        "INV-0001",
        batch.number,
        "20.000",
        None,
    )
    wrong = client.put(
        reverse("count-lines", args=[body["id"]]),
        {"lines": [{"line": line["id"], "counted_quantity": "x"}]},
        format="json",
    )
    assert list(wrong.json()) == ["lines.0.counted_quantity"]
    saved = client.put(
        reverse("count-lines", args=[body["id"]]),
        {"lines": [{"line": line["id"], "counted_quantity": "19.250"}]},
        format="json",
    )
    assert saved.json()["lines"][0]["difference"] == "-0.750"
    approved = client.post(reverse("count-approve", args=[body["id"]]))
    assert (approved.status_code, approved.json()["status"]) == (200, "approved")
    assert selectors.quantity_on_hand(organization, location_id=room.pk) == Decimal("19.250")
    assert client.get(reverse("count-list"), {"status": "approved"}).json()["count"] == 1
    assert client.post(reverse("count-cancel", args=[body["id"]])).status_code == 400


@pytest.mark.parametrize(
    ("role", "read_status", "write_status"), [(Role.ACCOUNTANT, 200, 403), (Role.DRIVER, 403, 403)]
)
def test_the_accountant_reads_counts_and_drivers_get_nothing(role, read_status, write_status):
    client, _ = client_for(role)

    assert client.get(reverse("count-list")).status_code == read_status
    assert client.post(reverse("count-list"), {}, format="json").status_code == write_status


def test_another_organization_counts_are_invisible():
    client, _ = client_for(Role.OWNER)
    other = OrganizationFactory.create()
    room = StockLocationFactory.create(organization=other)
    receive(other, room, "5")
    count = start(other, None, room)

    assert client.get(reverse("count-list")).json()["count"] == 0
    assert client.get(reverse("count-detail", args=[count.pk])).status_code == 404
    assert client.post(reverse("count-approve", args=[count.pk])).status_code == 404
