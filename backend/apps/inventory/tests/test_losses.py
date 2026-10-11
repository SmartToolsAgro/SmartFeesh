import datetime as dt
import io
import uuid
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.catalog.tests.factories import ProductFactory
from apps.core.models import AuditLog, Role
from apps.core.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.inventory import selectors, services
from apps.inventory.models import LocationKind, LossReason, LossStatus, MovementKind, StockLoss, StockMovement

from .factories import BatchFactory, StockLocationFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def organization():
    return OrganizationFactory.create()


@pytest.fixture
def actor():
    return UserFactory.create()


@pytest.fixture
def truck(organization):
    return StockLocationFactory.create(organization=organization, kind=LocationKind.TRUCK, name="Camion 1")


@pytest.fixture
def mussels(organization):
    return ProductFactory.create(organization=organization, name="Moules")


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def receive(organization, product, location, kg, *, days_ago=0, cost="10"):
    batch = BatchFactory.create(
        organization=organization,
        product=product,
        received_on=timezone.localdate() - dt.timedelta(days=days_ago),
        unit_cost=Decimal(cost),
    )
    services.post_movement(
        organization=organization, actor=None, kind=MovementKind.RECEIPT, batch=batch, quantity=kg, to_location=location
    )
    return batch


def lose(organization, actor, location, product, kg, **fields):
    values: dict[str, Any] = {"reason": LossReason.SPOILED, "lost_on": timezone.localdate()}
    values.update(fields)
    return services.record_loss(
        organization=organization, actor=actor, location=location, product=product, quantity=kg, **values
    )


def image_upload():
    buffer = io.BytesIO()
    Image.new("RGB", (800, 600), (200, 80, 60)).save(buffer, format="JPEG")
    return SimpleUploadedFile("loss.jpg", buffer.getvalue(), content_type="image/jpeg")


# ---- services ----


def test_a_small_loss_leaves_the_stock_at_once_oldest_batch_first(organization, actor, truck, mussels):
    old = receive(organization, mussels, truck, "1", days_ago=2, cost="8")
    recent = receive(organization, mussels, truck, "5", cost="9")

    loss = lose(organization, actor, truck, mussels, "1.5", note="Sac percé")

    assert (loss.number, loss.status, loss.decided_by) == ("PE-0001", LossStatus.APPROVED, actor)
    moved = selectors.movements_from_sources([loss])[loss.pk]
    assert [(movement.batch, movement.quantity, movement.kind) for movement in moved] == [
        (old, Decimal("1.000"), MovementKind.LOSS),
        (recent, Decimal("0.500"), MovementKind.LOSS),
    ]
    assert moved[0].reason == "Avarié · Sac percé"
    assert selectors.quantity_on_hand(organization, location_id=truck.pk) == Decimal("4.500")


def test_above_the_threshold_a_loss_waits_for_the_owner(organization, actor, truck, mussels):
    receive(organization, mussels, truck, "10")

    loss = lose(organization, actor, truck, mussels, "2.001")

    assert (loss.status, loss.decided_by) == (LossStatus.PENDING, None)
    assert selectors.quantity_on_hand(organization, location_id=truck.pk) == Decimal("10.000")
    approved = services.approve_loss(loss=loss, actor=actor)
    assert approved.status == LossStatus.APPROVED
    assert selectors.quantity_on_hand(organization, location_id=truck.pk) == Decimal("7.999")
    with pytest.raises(ValidationError, match="déjà décidée"):
        services.approve_loss(loss=loss, actor=actor)
    with pytest.raises(ValidationError, match="déjà décidée"):
        services.reject_loss(loss=loss, actor=actor, reason="Non")


def test_the_owner_never_waits_and_the_threshold_can_change(organization, actor, truck, mussels):
    receive(organization, mussels, truck, "10")

    assert lose(organization, actor, truck, mussels, "5", may_approve=True).status == LossStatus.APPROVED
    services.update_stock_settings(organization=organization, actor=actor, loss_approval_threshold="0")
    assert lose(organization, actor, truck, mussels, "0.1").status == LossStatus.PENDING
    services.update_stock_settings(organization=organization, actor=actor, loss_approval_threshold="10")
    assert lose(organization, actor, truck, mussels, "4").status == LossStatus.APPROVED
    assert selectors.stock_settings(organization).loss_approval_threshold == Decimal("10.000")
    assert AuditLog.objects.filter(action="stock.settings_updated").count() == 2
    with pytest.raises(ValidationError) as refused:
        services.update_stock_settings(organization=organization, actor=actor, loss_approval_threshold="-1")
    assert list(refused.value.message_dict) == ["loss_approval_threshold"]


def test_a_rejected_loss_moves_nothing_and_needs_a_reason(organization, actor, truck, mussels):
    receive(organization, mussels, truck, "10")
    loss = lose(organization, actor, truck, mussels, "3")

    with pytest.raises(ValidationError) as no_reason:
        services.reject_loss(loss=loss, actor=actor, reason="  ")
    assert list(no_reason.value.message_dict) == ["reason"]
    rejected = services.reject_loss(loss=loss, actor=actor, reason="Vendu en fait")

    assert (rejected.status, rejected.rejection_reason) == (LossStatus.REJECTED, "Vendu en fait")
    assert not StockMovement.objects.filter(kind=MovementKind.LOSS).exists()


def test_a_loss_is_checked_on_each_field(organization, actor, truck, mussels):
    receive(organization, mussels, truck, "2")
    archived = StockLocationFactory.create(organization=organization, is_active=False)

    with pytest.raises(ValidationError) as more:
        lose(organization, actor, truck, mussels, "3")
    assert "Stock insuffisant" in more.value.message_dict["quantity"][0]
    with pytest.raises(ValidationError) as wrong:
        lose(
            organization,
            actor,
            archived,
            ProductFactory.create(),
            "1,5",
            reason="stolen",
            lost_on=timezone.localdate() + dt.timedelta(days=1),
        )
    assert set(wrong.value.message_dict) == {"location", "product", "quantity", "reason", "lost_on"}
    assert not StockLoss.objects.exists()


def test_a_waiting_loss_bigger_than_what_is_left_is_refused_at_approval(organization, actor, truck, mussels):
    receive(organization, mussels, truck, "5")
    loss = lose(organization, actor, truck, mussels, "4")
    lose(organization, actor, truck, mussels, "2")  # under the threshold: gone at once

    with pytest.raises(ValidationError) as refused:
        services.approve_loss(loss=loss, actor=actor)

    assert list(refused.value.message_dict) == ["quantity"]
    loss.refresh_from_db()
    assert loss.status == LossStatus.PENDING


def test_the_same_client_uuid_records_one_loss(organization, actor, truck, mussels):
    receive(organization, mussels, truck, "5")
    key = uuid.uuid4()

    first = lose(organization, actor, truck, mussels, "1", client_uuid=key)
    again = lose(organization, actor, truck, mussels, "1", client_uuid=key)

    assert again == first
    assert selectors.quantity_on_hand(organization, location_id=truck.pk) == Decimal("4.000")


def test_a_photo_is_joined_once(organization, actor, truck, mussels, media):
    receive(organization, mussels, truck, "5")
    loss = lose(organization, actor, truck, mussels, "1")

    with_photo = services.add_loss_photo(loss=loss, actor=actor, upload=image_upload())

    assert str(with_photo.photo.name).startswith(f"losses/{organization.pk}/")
    assert str(with_photo.photo.name).endswith(".webp")
    with pytest.raises(ValidationError) as again:
        services.add_loss_photo(loss=with_photo, actor=actor, upload=image_upload())
    assert list(again.value.message_dict) == ["photo"]
    with pytest.raises(ValidationError):
        services.add_loss_photo(
            loss=lose(organization, actor, truck, mussels, "1"),
            actor=actor,
            upload=SimpleUploadedFile("notes.txt", b"pas une image", content_type="text/plain"),
        )


# ---- API ----


def client_for(role, organization=None):
    membership = MembershipFactory.create(role=role, organization=organization or OrganizationFactory.create())
    client = APIClient()
    client.force_authenticate(membership.user)
    return client, membership


def payload(location, product, **fields):
    body = {
        "location": location.pk,
        "product": product.pk,
        "quantity": "3",
        "reason": "spoiled",
        "lost_on": timezone.localdate().isoformat(),
        "note": "Odeur",
    }
    body.update(fields)
    return body


def test_a_manager_loss_above_the_threshold_waits_and_only_the_owner_decides(media):
    manager_client, manager = client_for(Role.MANAGER)
    organization = manager.organization
    owner_client, _ = client_for(Role.OWNER, organization)
    truck = StockLocationFactory.create(organization=organization, kind=LocationKind.TRUCK)
    product = ProductFactory.create(organization=organization)
    batch = receive(organization, product, truck, "10", cost="12.5")

    created = manager_client.post(reverse("loss-list"), payload(truck, product), format="json")

    assert created.status_code == 201
    body = created.json()
    assert (body["number"], body["status"], body["batches"], body["cost_amount"]) == ("PE-0001", "pending", [], None)
    assert manager_client.post(reverse("loss-approve", args=[body["id"]])).status_code == 403
    assert manager_client.post(reverse("loss-reject", args=[body["id"]]), {"reason": "x"}).status_code == 403
    photo = manager_client.put(reverse("loss-photo", args=[body["id"]]), {"photo": image_upload()}, format="multipart")
    assert photo.status_code == 200
    assert photo.json()["photo_url"] == reverse("loss-photo", args=[body["id"]])
    assert manager_client.get(photo.json()["photo_url"]).status_code == 200

    approved = owner_client.post(reverse("loss-approve", args=[body["id"]]))
    assert approved.status_code == 200
    assert (approved.json()["status"], approved.json()["cost_amount"]) == ("approved", "37.500")
    assert approved.json()["batches"] == [{"batch_id": batch.pk, "batch_number": batch.number, "quantity": "3.000"}]
    listed = manager_client.get(reverse("loss-list"), {"status": "approved"}).json()
    assert (listed["count"], listed["results"][0]["number"]) == (1, "PE-0001")


def test_the_owner_records_at_once_and_sets_the_threshold():
    owner_client, owner = client_for(Role.OWNER)
    organization = owner.organization
    manager_client, _ = client_for(Role.MANAGER, organization)
    room = StockLocationFactory.create(organization=organization)
    product = ProductFactory.create(organization=organization)
    receive(organization, product, room, "10")

    assert owner_client.post(reverse("loss-list"), payload(room, product), format="json").json()["status"] == "approved"
    assert owner_client.get(reverse("stock-settings")).json() == {"loss_approval_threshold": "2.000"}
    assert manager_client.put(reverse("stock-settings"), {"loss_approval_threshold": "5"}).status_code == 403
    changed = owner_client.put(reverse("stock-settings"), {"loss_approval_threshold": "5"}, format="json")
    assert changed.json() == {"loss_approval_threshold": "5.000"}
    assert manager_client.post(reverse("loss-list"), payload(room, product), format="json").json()["status"] == (
        "approved"
    )
    refused = manager_client.post(reverse("loss-list"), payload(room, product, quantity="99"), format="json")
    assert list(refused.json()) == ["quantity"]


@pytest.mark.parametrize(
    ("role", "read_status", "write_status"), [(Role.ACCOUNTANT, 200, 403), (Role.DRIVER, 403, 403)]
)
def test_the_accountant_reads_and_drivers_get_nothing(role, read_status, write_status):
    client, _ = client_for(role)

    assert client.get(reverse("loss-list")).status_code == read_status
    assert client.post(reverse("loss-list"), {}, format="json").status_code == write_status
    assert client.get(reverse("stock-settings")).status_code == read_status


def test_another_organization_losses_are_invisible():
    client, _ = client_for(Role.OWNER)
    other = OrganizationFactory.create()
    room = StockLocationFactory.create(organization=other)
    product = ProductFactory.create(organization=other)
    receive(other, product, room, "5")
    loss = lose(other, None, room, product, "1")

    assert client.get(reverse("loss-list")).json()["count"] == 0
    assert client.get(reverse("loss-detail", args=[loss.pk])).status_code == 404
    assert client.post(reverse("loss-approve", args=[loss.pk])).status_code == 404
    assert client.post(reverse("loss-list"), payload(room, product), format="json").status_code == 400
