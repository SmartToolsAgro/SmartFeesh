"""Paramètres > company profile and user management (owner request, D-123)."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.core import audit
from apps.core.models import Membership, Role, User

from .factories import MembershipFactory, OrganizationFactory, UserFactory

pytestmark = pytest.mark.django_db

NEW_PASSWORD = "Sakiet-Ezzit-99"


def client_for(role, organization=None, **membership_fields):
    membership = MembershipFactory.create(
        role=role,
        organization=organization or OrganizationFactory.create(),
        user=UserFactory.create(),
        **membership_fields,
    )
    client = APIClient()
    client.force_authenticate(membership.user)
    return client, membership


def _photo() -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), "blue").save(buffer, format="PNG")
    return SimpleUploadedFile("photo.png", buffer.getvalue(), content_type="image/png")


# ---- Owner-only users management ----


@pytest.mark.parametrize("role", [Role.MANAGER, Role.ACCOUNTANT, Role.DRIVER])
def test_only_the_owner_manages_users(role):
    """A manager, accountant or driver may not list, create, or change another member (D-123)."""
    client, membership = client_for(role)
    colleague = MembershipFactory.create(organization=membership.organization, role=Role.DRIVER)

    assert client.get(reverse("member-list")).status_code == 403
    assert client.post(reverse("member-list"), {}, format="json").status_code == 403
    assert (
        client.patch(reverse("member-role", args=[colleague.pk]), {"role": "manager"}, format="json").status_code == 403
    )
    assert client.post(reverse("member-deactivate", args=[colleague.pk])).status_code == 403
    assert (
        client.post(
            reverse("member-reset-password"[:0] or "member-reset-password", args=[colleague.pk])
            if False
            else reverse("member-reset-password", args=[colleague.pk]),
            {"new_password": NEW_PASSWORD},
            format="json",
        ).status_code
        == 403
    )


def test_the_owner_creates_a_member_with_a_role_and_can_log_them_in():
    client, owner = client_for(Role.OWNER)

    response = client.post(
        reverse("member-list"),
        {
            "username": "nouveau",
            "password": NEW_PASSWORD,
            "role": "manager",
            "first_name": "Sami",
            "last_name": "Trabelsi",
            "email": "sami@example.com",
        },
        format="json",
    )

    assert response.status_code == 201, response.json()
    created = User.objects.get(username="nouveau")
    assert created.check_password(NEW_PASSWORD)
    assert Membership.objects.get(user=created, organization=owner.organization).role == Role.MANAGER

    other_client = APIClient()
    assert (
        other_client.post(
            reverse("auth-login"), {"username": "nouveau", "password": NEW_PASSWORD}, format="json"
        ).status_code
        == 200
    )


def test_creating_a_member_with_a_taken_username_is_refused():
    client, _ = client_for(Role.OWNER)
    UserFactory.create(username="prise")

    response = client.post(
        reverse("member-list"),
        {"username": "prise", "password": NEW_PASSWORD, "role": "driver"},
        format="json",
    )

    assert response.status_code == 400
    assert "username" in response.json()


def test_a_weak_password_is_refused_when_creating_a_member():
    client, _ = client_for(Role.OWNER)

    response = client.post(
        reverse("member-list"),
        {"username": "faible", "password": "1234", "role": "driver"},
        format="json",
    )

    assert response.status_code == 400


def test_the_owner_changes_a_role_deactivates_and_reactivates_a_member():
    client, owner = client_for(Role.OWNER)
    colleague = MembershipFactory.create(organization=owner.organization, role=Role.DRIVER)

    changed = client.patch(reverse("member-role", args=[colleague.pk]), {"role": "manager"}, format="json")
    assert changed.status_code == 200
    assert changed.json()["role"] == "manager"

    deactivated = client.post(reverse("member-deactivate", args=[colleague.pk]))
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    colleague.refresh_from_db()
    colleague.user.refresh_from_db()
    assert colleague.is_active is False
    assert colleague.user.is_active is False
    # A deactivated user cannot log back in (D-123: deactivate, never delete).
    deactivated_client = APIClient()
    deactivated_client.force_authenticate(colleague.user)
    assert deactivated_client.get(reverse("me")).status_code == 403

    reactivated = client.post(reverse("member-reactivate", args=[colleague.pk]))
    assert reactivated.status_code == 200
    colleague = Membership.objects.select_related("user").get(pk=colleague.pk)
    assert colleague.is_active is True
    assert colleague.user.is_active is True


def test_the_owner_cannot_strip_the_last_active_owner():
    client, owner = client_for(Role.OWNER)

    demoted = client.patch(reverse("member-role", args=[owner.pk]), {"role": "manager"}, format="json")
    assert demoted.status_code == 400
    owner.refresh_from_db()
    assert owner.role == Role.OWNER

    deactivated = client.post(reverse("member-deactivate", args=[owner.pk]))
    assert deactivated.status_code == 400
    owner.refresh_from_db()
    assert owner.is_active is True


def test_a_second_owner_may_still_be_demoted_or_deactivated():
    client, owner = client_for(Role.OWNER)
    second_owner = MembershipFactory.create(organization=owner.organization, role=Role.OWNER)

    assert (
        client.patch(reverse("member-role", args=[second_owner.pk]), {"role": "manager"}, format="json").status_code
        == 200
    )


def test_the_owner_resets_a_member_s_password():
    client, owner = client_for(Role.OWNER)
    colleague = MembershipFactory.create(organization=owner.organization, role=Role.DRIVER)

    response = client.post(
        reverse("member-reset-password", args=[colleague.pk]), {"new_password": NEW_PASSWORD}, format="json"
    )

    assert response.status_code == 204
    colleague.user.refresh_from_db()
    assert colleague.user.check_password(NEW_PASSWORD)


def test_a_member_of_another_organization_is_a_404_not_a_403():
    """Org scoping (D-022): the owner cannot even see that the id belongs to another company."""
    client, _ = client_for(Role.OWNER)
    stranger = MembershipFactory.create(role=Role.DRIVER)  # another organization

    assert (
        client.patch(reverse("member-role", args=[stranger.pk]), {"role": "manager"}, format="json").status_code == 404
    )
    assert client.post(reverse("member-deactivate", args=[stranger.pk])).status_code == 404
    assert (
        client.post(
            reverse("member-reset-password", args=[stranger.pk]), {"new_password": NEW_PASSWORD}, format="json"
        ).status_code
        == 404
    )


# ---- Self-service: any logged-in user ----


@pytest.mark.parametrize("role", [Role.OWNER, Role.MANAGER, Role.ACCOUNTANT, Role.DRIVER])
def test_every_role_may_update_their_own_profile_and_password(role):
    client, membership = client_for(role)

    profile = client.patch(reverse("my-profile"), {"first_name": "Nouveau", "last_name": "Nom"}, format="json")
    assert profile.status_code == 200
    assert profile.json()["user"]["first_name"] == "Nouveau"

    changed = client.post(
        reverse("my-password"), {"old_password": "test-password", "new_password": NEW_PASSWORD}, format="json"
    )
    assert changed.status_code == 204
    membership.user.refresh_from_db()
    assert membership.user.check_password(NEW_PASSWORD)
    assert client.get(reverse("me")).status_code == 200


def test_changing_the_password_needs_the_real_old_one():
    client, membership = client_for(Role.OWNER)

    response = client.post(
        reverse("my-password"), {"old_password": "wrong", "new_password": NEW_PASSWORD}, format="json"
    )

    assert response.status_code == 400
    membership.user.refresh_from_db()
    assert membership.user.check_password("test-password")


def test_a_member_cannot_reach_another_organization_s_member_management_through_their_own_org():
    """An owner's member endpoints only ever see their own organization's rows (D-022)."""
    client, _ = client_for(Role.OWNER)
    other_org_colleague = MembershipFactory.create(role=Role.DRIVER)

    listed = client.get(reverse("member-list"))
    assert other_org_colleague.user.username not in {row["user"]["username"] for row in listed.json()}


# ---- Avatars and the company logo ----


def test_a_user_uploads_and_removes_their_own_avatar():
    client, membership = client_for(Role.DRIVER)

    uploaded = client.put(reverse("my-avatar"), {"photo": _photo()}, format="multipart")
    assert uploaded.status_code == 200
    assert uploaded.json()["user"]["avatar_url"]

    membership.user.refresh_from_db()
    url = reverse("user-avatar", args=[membership.user.pk])
    photo = client.get(url)
    assert photo.status_code == 200
    assert photo["Content-Type"] == "image/webp"

    removed = client.delete(reverse("my-avatar"))
    assert removed.status_code == 200
    assert removed.json()["user"]["avatar_url"] is None


def test_a_colleague_in_the_same_organization_can_see_the_avatar_but_a_stranger_cannot():
    client, membership = client_for(Role.DRIVER)
    client.put(reverse("my-avatar"), {"photo": _photo()}, format="multipart")

    colleague, _ = client_for(Role.MANAGER, organization=membership.organization)
    assert colleague.get(reverse("user-avatar", args=[membership.user.pk])).status_code == 200

    stranger, _ = client_for(Role.OWNER)
    assert stranger.get(reverse("user-avatar", args=[membership.user.pk])).status_code == 404


def test_the_owner_and_manager_change_the_company_logo_but_the_accountant_only_reads():
    owner, owner_membership = client_for(Role.OWNER)
    accountant, _ = client_for(Role.ACCOUNTANT, organization=owner_membership.organization)
    org = owner_membership.organization

    uploaded = owner.put(reverse("organization-logo", args=[org.pk]), {"photo": _photo()}, format="multipart")
    assert uploaded.status_code == 200
    assert uploaded.json()["logo_url"]

    assert (
        accountant.put(reverse("organization-logo", args=[org.pk]), {"photo": _photo()}, format="multipart").status_code
        == 403
    )
    assert accountant.get(reverse("organization-logo", args=[org.pk])).status_code == 200

    removed = owner.delete(reverse("organization-logo", args=[org.pk]))
    assert removed.status_code == 200
    assert removed.json()["logo_url"] is None


def test_the_company_logo_of_another_organization_is_not_served():
    owner, owner_membership = client_for(Role.OWNER)
    owner.put(
        reverse("organization-logo", args=[owner_membership.organization.pk]), {"photo": _photo()}, format="multipart"
    )

    other_owner, _ = client_for(Role.OWNER)
    assert other_owner.get(reverse("organization-logo", args=[owner_membership.organization.pk])).status_code == 404


# ---- Owner edits a member's identifier and name, and deletes an unused account (D-143) ----


@pytest.mark.parametrize("role", [Role.MANAGER, Role.ACCOUNTANT, Role.DRIVER])
def test_only_the_owner_edits_or_deletes_a_member(role):
    client, membership = client_for(role)
    colleague = MembershipFactory.create(organization=membership.organization, role=Role.DRIVER)

    patched = client.patch(
        reverse("member-detail", args=[colleague.pk]), {"username": "autre", "first_name": "X"}, format="json"
    )
    assert patched.status_code == 403
    assert client.delete(reverse("member-detail", args=[colleague.pk])).status_code == 403
    colleague.user.refresh_from_db()
    assert colleague.user.username != "autre"
    assert Membership.objects.filter(pk=colleague.pk).exists()


def test_the_owner_corrects_a_members_identifier_and_name():
    client, owner = client_for(Role.OWNER)
    colleague = MembershipFactory.create(organization=owner.organization, role=Role.DRIVER)

    response = client.patch(
        reverse("member-detail", args=[colleague.pk]),
        {"username": "sami.b", "first_name": "Sami", "last_name": "Bouzid"},
        format="json",
    )

    assert response.status_code == 200, response.json()
    assert response.json()["user"]["username"] == "sami.b"
    assert response.json()["user"]["last_name"] == "Bouzid"
    colleague.user.refresh_from_db()
    assert colleague.user.username == "sami.b"
    assert colleague.user.first_name == "Sami"


def test_a_taken_identifier_is_refused_when_editing_a_member():
    client, owner = client_for(Role.OWNER)
    colleague = MembershipFactory.create(organization=owner.organization, role=Role.DRIVER)
    UserFactory.create(username="prise")

    response = client.patch(reverse("member-detail", args=[colleague.pk]), {"username": "prise"}, format="json")

    assert response.status_code == 400
    assert "username" in response.json()
    colleague.user.refresh_from_db()
    assert colleague.user.username != "prise"


def test_the_owner_deletes_an_account_without_history():
    client, owner = client_for(Role.OWNER)
    colleague = MembershipFactory.create(organization=owner.organization, role=Role.DRIVER)
    user_id = colleague.user_id

    response = client.delete(reverse("member-detail", args=[colleague.pk]))

    assert response.status_code == 204
    assert not User.objects.filter(pk=user_id).exists()
    assert not Membership.objects.filter(pk=colleague.pk).exists()


def test_an_account_with_history_cannot_be_deleted_only_deactivated():
    client, owner = client_for(Role.OWNER)
    colleague = MembershipFactory.create(organization=owner.organization, role=Role.DRIVER)
    # Their name is on an audit entry (the actor of a recorded action): the history must stay.
    audit.record(organization=owner.organization, actor=colleague.user, action="test.something")

    response = client.delete(reverse("member-detail", args=[colleague.pk]))

    assert response.status_code == 400
    assert User.objects.filter(pk=colleague.user_id).exists()
    assert Membership.objects.filter(pk=colleague.pk).exists()


def test_the_owner_cannot_delete_their_own_account():
    client, owner = client_for(Role.OWNER)
    MembershipFactory.create(organization=owner.organization, role=Role.OWNER)  # a second owner, so not the last

    response = client.delete(reverse("member-detail", args=[owner.pk]))

    assert response.status_code == 400
    assert Membership.objects.filter(pk=owner.pk).exists()
