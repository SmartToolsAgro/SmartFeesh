from decimal import Decimal

import pytest

from apps.core import audit, services
from apps.core.models import AuditLog, Role

from .factories import OrganizationFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_record_stores_who_what_and_the_values_before_and_after():
    organization, actor = OrganizationFactory.create(), UserFactory.create()

    entry = audit.record(
        organization=organization,
        actor=actor,
        action="organization.renamed",
        target=organization,
        before={"name": "Ancien nom"},
        after={"name": organization.name},
    )

    saved = AuditLog.objects.get(pk=entry.pk)
    assert saved.organization == organization
    assert saved.actor == actor
    assert saved.action == "organization.renamed"
    assert saved.target == organization
    assert saved.target_repr == organization.name
    assert saved.before == {"name": "Ancien nom"}
    assert saved.after == {"name": organization.name}
    assert saved.created_at is not None


def test_amounts_are_stored_as_strings_without_losing_precision():
    entry = audit.record(
        organization=OrganizationFactory.create(),
        actor=None,
        action="test.amount",
        after={"total": Decimal("1250.005")},
    )

    assert AuditLog.objects.get(pk=entry.pk).after == {"total": "1250.005"}


def test_entries_cannot_be_changed_or_deleted():
    entry = audit.record(organization=OrganizationFactory.create(), actor=None, action="test.locked")

    entry.action = "test.tampered"
    with pytest.raises(TypeError):
        entry.save()
    with pytest.raises(TypeError):
        entry.delete()
    # Bulk operations are refused too, so a queryset cannot bypass the rule.
    with pytest.raises(TypeError):
        AuditLog.objects.filter(pk=entry.pk).update(action="test.tampered")
    with pytest.raises(TypeError):
        AuditLog.objects.filter(pk=entry.pk).delete()
    assert AuditLog.objects.get(pk=entry.pk).action == "test.locked"


def test_changing_a_role_writes_an_audit_entry():
    organization, owner, user = OrganizationFactory.create(), UserFactory.create(), UserFactory.create()
    services.add_member(organization=organization, user=user, role=Role.DRIVER, actor=owner)

    membership = services.add_member(organization=organization, user=user, role=Role.MANAGER, actor=owner)

    assert membership.role == Role.MANAGER
    assert user.memberships.count() == 1
    first, second = AuditLog.objects.for_organization(organization).order_by("id")
    assert (first.action, first.before, first.after) == (
        "membership.set",
        None,
        {"role": "driver", "is_active": True},
    )
    assert (second.before, second.after) == (
        {"role": "driver", "is_active": True},
        {"role": "manager", "is_active": True},
    )
    assert second.actor == owner
