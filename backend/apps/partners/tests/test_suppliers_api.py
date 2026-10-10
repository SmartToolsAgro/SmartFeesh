import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.models import Role
from apps.core.tests.factories import MembershipFactory

from .factories import SupplierContactFactory, SupplierFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def manager():
    return MembershipFactory.create(role=Role.MANAGER)


def client_for(membership):
    client = APIClient()
    client.force_authenticate(membership.user)
    return client


@pytest.fixture
def api(manager):
    return client_for(manager)


def create(api, **fields):
    payload = {"name": "Pêcherie Kerkennah"}
    payload.update(fields)
    return api.post(reverse("supplier-list"), payload, format="json")


def test_creating_a_supplier_answers_it_with_its_contacts(api):
    response = create(
        api,
        tax_id="0000001a/a/m/000",
        city="Kerkennah",
        contacts=[{"name": "Hédi", "phone": "+216 98 000 001"}],
    )

    assert response.status_code == 201
    body = response.json()
    assert body["reference"] == "F-001"
    assert body["tax_id"] == "0000001A/A/M/000"
    assert body["contacts"] == [{"name": "Hédi", "role": "", "phone": "+216 98 000 001", "email": ""}]
    assert body["is_active"] is True


def test_a_business_rule_error_is_a_400_on_its_field(api):
    response = create(api, tax_id="12AB")

    assert response.status_code == 400
    assert list(response.json()) == ["tax_id"]


def test_a_contact_without_name_is_a_400(api):
    response = create(api, contacts=[{"phone": "+216 98 000 001"}])

    assert response.status_code == 400
    assert "contacts" in response.json()


@pytest.mark.parametrize(
    ("role", "read_status", "write_status"),
    [
        (Role.OWNER, 200, 201),
        (Role.MANAGER, 200, 201),
        (Role.ACCOUNTANT, 200, 403),
        (Role.DRIVER, 403, 403),
    ],
)
def test_drivers_never_see_suppliers_and_accountants_only_read(role, read_status, write_status):
    client = client_for(MembershipFactory.create(role=role))

    assert client.get(reverse("supplier-list")).status_code == read_status
    assert create(client).status_code == write_status


def test_anonymous_visitors_get_401():
    assert APIClient().get(reverse("supplier-list")).status_code == 401


def test_another_organization_suppliers_are_invisible(api):
    other = SupplierFactory.create()

    assert api.get(reverse("supplier-list")).json() == []
    assert api.get(reverse("supplier-detail", args=[other.pk])).status_code == 404
    assert api.patch(reverse("supplier-detail", args=[other.pk]), {"name": "X"}, format="json").status_code == 404
    assert api.post(reverse("supplier-archive", args=[other.pk])).status_code == 404


def test_the_list_filters_by_search_and_status(api, manager):
    kerkennah = SupplierFactory.create(organization=manager.organization, name="Pêcherie Kerkennah")
    SupplierContactFactory.create(supplier=kerkennah, name="Hédi")
    SupplierFactory.create(organization=manager.organization, name="Aqua Monastir", is_active=False)

    def names(**params):
        return [row["name"] for row in api.get(reverse("supplier-list"), params).json()]

    assert names() == ["Pêcherie Kerkennah"]
    assert names(status="all") == ["Aqua Monastir", "Pêcherie Kerkennah"]
    assert names(status="archived") == ["Aqua Monastir"]
    assert names(search="hédi") == ["Pêcherie Kerkennah"]
    assert api.get(reverse("supplier-list"), {"status": "gone"}).status_code == 400


def test_a_partial_update_keeps_the_other_fields_and_the_contacts(api):
    supplier_id = create(api, city="Kerkennah", contacts=[{"name": "Hédi"}]).json()["id"]

    response = api.patch(reverse("supplier-detail", args=[supplier_id]), {"phone": "+216 74 000 101"}, format="json")

    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["city"], body["phone"]) == ("Pêcherie Kerkennah", "Kerkennah", "+216 74 000 101")
    assert [contact["name"] for contact in body["contacts"]] == ["Hédi"]


def test_sending_contacts_replaces_them(api):
    supplier_id = create(api, contacts=[{"name": "Hédi"}, {"name": "Amel"}]).json()["id"]

    response = api.patch(
        reverse("supplier-detail", args=[supplier_id]), {"contacts": [{"name": "Amel"}]}, format="json"
    )

    assert [contact["name"] for contact in response.json()["contacts"]] == ["Amel"]


def test_archiving_and_restoring(api):
    supplier_id = create(api).json()["id"]

    archived = api.post(reverse("supplier-archive", args=[supplier_id]))
    assert archived.status_code == 200
    assert archived.json()["is_active"] is False
    assert api.get(reverse("supplier-list")).json() == []
    assert api.get(reverse("supplier-detail", args=[supplier_id])).status_code == 200

    restored = api.post(reverse("supplier-restore", args=[supplier_id]))
    assert restored.json()["is_active"] is True
