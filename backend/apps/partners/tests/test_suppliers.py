from typing import Any

import pytest
from django.core.exceptions import ValidationError

from apps.core.models import AuditLog
from apps.core.tests.factories import OrganizationFactory, UserFactory
from apps.partners import selectors, services

from .factories import SupplierContactFactory, SupplierFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def organization():
    return OrganizationFactory.create()


@pytest.fixture
def actor():
    return UserFactory.create()


def new_supplier(organization, actor, **fields):
    values: dict[str, Any] = {"name": "Pêcherie Kerkennah"}
    values.update(fields)
    return services.create_supplier(organization=organization, actor=actor, **values)


# ---- tax ID ----


@pytest.mark.parametrize(
    ("typed", "stored"),
    [
        ("1234567A/A/M/000", "1234567A/A/M/000"),
        ("1234567 a a m 000", "1234567A/A/M/000"),
        ("1234567-A/P/C/001", "1234567A/P/C/001"),
        ("123456B", "0123456B"),
        ("  ", ""),
    ],
)
def test_a_tax_id_is_stored_the_usual_way(typed, stored):
    assert services.normalized_tax_id(typed) == stored


@pytest.mark.parametrize("typed", ["12345A", "1234567", "1234567A/A/M", "1234567A/A/M/00", "ABCDEFGH"])
def test_a_tax_id_of_another_shape_is_refused(typed):
    with pytest.raises(ValueError, match="Matricule fiscal"):
        services.normalized_tax_id(typed)


# ---- creating ----


def test_a_supplier_without_reference_gets_the_next_one(organization, actor):
    SupplierFactory.create(organization=organization, reference="F-007")
    SupplierFactory.create(organization=organization, reference="PECH-12")
    SupplierFactory.create(reference="F-050")  # another company

    supplier = new_supplier(organization, actor)

    assert supplier.reference == "F-008"
    assert new_supplier(organization, actor, name="Aqua Monastir").reference == "F-009"


def test_the_first_generated_reference_is_f_001(organization, actor):
    assert new_supplier(organization, actor).reference == "F-001"


def test_creating_cleans_the_fields_stores_the_contacts_and_is_audited(organization, actor):
    supplier = new_supplier(
        organization,
        actor,
        reference=" F-001 ",
        tax_id="0000001a/a/m/000",
        phone=" +216 74 000 101 ",
        city="Kerkennah",
        contacts=[{"name": " Hédi ", "role": "Armateur", "phone": "+216 98 000 001"}],
    )

    assert (supplier.reference, supplier.tax_id, supplier.phone) == ("F-001", "0000001A/A/M/000", "+216 74 000 101")
    contact = supplier.contacts.get()
    assert (contact.name, contact.role, contact.organization) == ("Hédi", "Armateur", organization)
    entry = AuditLog.objects.get(action="supplier.created")
    assert entry.actor == actor
    assert entry.after is not None
    assert entry.after["contacts"] == [{"name": "Hédi", "role": "Armateur", "phone": "+216 98 000 001", "email": ""}]


def test_errors_come_one_per_field(organization, actor):
    SupplierFactory.create(organization=organization, reference="F-001", tax_id="0000001A/A/M/000")

    with pytest.raises(ValidationError) as caught:
        new_supplier(organization, actor, reference="f-001", name=" ", tax_id="0000001A/A/M/000", email="not-mail")

    assert set(caught.value.message_dict) == {"reference", "name", "tax_id", "email"}


def test_references_and_tax_ids_may_repeat_in_another_organization(organization, actor):
    SupplierFactory.create(reference="F-001", tax_id="0000001A/A/M/000")

    supplier = new_supplier(organization, actor, reference="F-001", tax_id="0000001A/A/M/000")

    assert supplier.pk is not None


def test_several_suppliers_may_have_no_tax_id(organization, actor):
    new_supplier(organization, actor)
    new_supplier(organization, actor, name="Mareyeur Port de Sfax")

    assert selectors.suppliers_of(organization).filter(tax_id="").count() == 2


def test_a_contact_needs_a_name(organization, actor):
    with pytest.raises(ValidationError) as caught:
        new_supplier(organization, actor, contacts=[{"name": "Hédi"}, {"name": " ", "phone": "+216 98"}])

    assert caught.value.message_dict == {"contacts": ["Contact 2 : le nom est obligatoire."]}
    assert not selectors.suppliers_of(organization).exists()


# ---- changing ----


def test_an_update_without_contacts_keeps_them_and_audits_only_what_changed(organization, actor):
    supplier = new_supplier(organization, actor, city="Sfax", contacts=[{"name": "Hédi"}])

    services.update_supplier(supplier=supplier, actor=actor, city="Kerkennah")

    supplier.refresh_from_db()
    assert supplier.city == "Kerkennah"
    assert list(supplier.contacts.values_list("name", flat=True)) == ["Hédi"]
    entry = AuditLog.objects.get(action="supplier.updated")
    assert (entry.before, entry.after) == ({"city": "Sfax"}, {"city": "Kerkennah"})


def test_an_update_with_contacts_replaces_the_list(organization, actor):
    supplier = new_supplier(organization, actor, contacts=[{"name": "Hédi"}, {"name": "Amel"}])

    services.update_supplier(supplier=supplier, actor=actor, contacts=[{"name": "Amel", "role": "Comptable"}])

    assert list(supplier.contacts.values_list("name", "role")) == [("Amel", "Comptable")]
    entry = AuditLog.objects.get(action="supplier.updated")
    assert entry.before is not None
    assert [contact["name"] for contact in entry.before["contacts"]] == ["Hédi", "Amel"]


def test_an_update_that_changes_nothing_is_not_audited(organization, actor):
    supplier = new_supplier(organization, actor, contacts=[{"name": "Hédi"}])

    services.update_supplier(supplier=supplier, actor=actor, name="Pêcherie Kerkennah", contacts=[{"name": "Hédi"}])

    assert not AuditLog.objects.filter(action="supplier.updated").exists()


def test_a_refused_update_changes_nothing(organization, actor):
    supplier = new_supplier(organization, actor, contacts=[{"name": "Hédi"}])

    with pytest.raises(ValidationError):
        services.update_supplier(supplier=supplier, actor=actor, name="Autre", contacts=[{"name": ""}])

    supplier.refresh_from_db()
    assert supplier.name == "Pêcherie Kerkennah"
    assert supplier.contacts.count() == 1


def test_archiving_and_restoring_are_audited_once(organization, actor):
    supplier = new_supplier(organization, actor)

    services.set_supplier_active(supplier=supplier, actor=actor, is_active=False)
    services.set_supplier_active(supplier=supplier, actor=actor, is_active=False)
    services.set_supplier_active(supplier=supplier, actor=actor, is_active=True)

    actions = AuditLog.objects.filter(target_id=str(supplier.pk)).order_by("id").values_list("action", flat=True)
    assert list(actions) == ["supplier.created", "supplier.archived", "supplier.restored"]


# ---- reading ----


def test_search_finds_a_supplier_once_by_name_city_or_contact(organization):
    sfax = SupplierFactory.create(organization=organization, name="Mareyeur Port de Sfax", city="Sfax")
    SupplierContactFactory.create(supplier=sfax, name="Karim Ben Ali")
    SupplierContactFactory.create(supplier=sfax, name="Karima")
    SupplierFactory.create(organization=organization, name="Aqua Monastir", city="Monastir")

    assert list(selectors.suppliers_of(organization, search="karim")) == [sfax]
    assert list(selectors.suppliers_of(organization, search="SFAX")) == [sfax]
    assert selectors.suppliers_of(organization, search="").count() == 2


def test_the_status_filter(organization):
    active = SupplierFactory.create(organization=organization)
    archived = SupplierFactory.create(organization=organization, is_active=False)

    assert list(selectors.suppliers_of(organization)) == [active]
    assert list(selectors.suppliers_of(organization, status="archived")) == [archived]
    assert selectors.suppliers_of(organization, status="all").count() == 2
