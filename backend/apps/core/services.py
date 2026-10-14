"""Every write on core models goes through these functions (ARCHITECTURE §3)."""

from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from . import audit, selectors
from .images import reencoded_photo
from .models import Job, JobRun, Membership, Organization, Role, User

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile


@transaction.atomic
def create_organization(*, name: str) -> Organization:
    return Organization.objects.create(name=name)


@transaction.atomic
def create_user(
    *,
    username: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    language: str = "fr",
) -> User:
    return User.objects.create_user(
        username=username,
        password=password,
        first_name=first_name,
        last_name=last_name,
        language=language,
    )


@transaction.atomic
def set_language(*, user: User, language: str) -> User:
    """Save the language the user wants the apps in."""
    if language not in dict(settings.LANGUAGES):
        raise ValueError(f"Unsupported language: {language}")
    user.language = language
    user.save(update_fields=["language"])
    return user


@transaction.atomic
def add_member(*, organization: Organization, user: User, role: Role, actor: User | None = None) -> Membership:
    """Give `user` a role in `organization`, or change the role they already have."""
    membership = Membership.objects.filter(organization=organization, user=user).first()
    before = {"role": membership.role, "is_active": membership.is_active} if membership else None
    if membership is None:
        membership = Membership(organization=organization, user=user)
    membership.role = role
    membership.is_active = True
    membership.save()
    audit.record(
        organization=organization,
        actor=actor,
        action="membership.set",
        target=membership,
        before=before,
        after={"role": membership.role, "is_active": True},
    )
    return membership


# ---- Paramètres: company profile and user management (owner request, D-123) ----


def _delete_file_after_commit(field: Any, name: str) -> None:
    storage = field.storage
    transaction.on_commit(lambda: storage.delete(name))


@transaction.atomic
def set_organization_logo(
    *, organization: Organization, actor: User | None, upload: "UploadedFile[bytes]"
) -> Organization:
    """Replace the company logo shown on the company-profile page. Turned upright, shrunk, saved as WebP."""
    content = reencoded_photo(upload, field="logo")
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    old_name = organization.logo.name or ""
    organization.logo.save("logo.webp", content, save=False)
    try:
        organization.save(update_fields=["logo", "updated_at"])
        audit.record(organization=organization, actor=actor, action="organization.logo_set", target=organization)
    except BaseException:
        # The file is written before the row: never leave it behind when the change is rolled back.
        if organization.logo.name:
            organization.logo.storage.delete(organization.logo.name)
        raise
    if old_name:
        _delete_file_after_commit(organization.logo, old_name)
    return organization


@transaction.atomic
def remove_organization_logo(*, organization: Organization, actor: User | None) -> Organization:
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    old_name = organization.logo.name or ""
    if old_name:
        organization.logo.name = ""
        organization.save(update_fields=["logo", "updated_at"])
        audit.record(organization=organization, actor=actor, action="organization.logo_removed", target=organization)
        _delete_file_after_commit(organization.logo, old_name)
    return organization


@transaction.atomic
def set_user_avatar(*, user: User, upload: "UploadedFile[bytes]") -> User:
    """A user's own photo, set from their profile menu. Nobody else may change it (D-123)."""
    content = reencoded_photo(upload, field="avatar")
    user = User.objects.select_for_update().get(pk=user.pk)
    old_name = user.avatar.name or ""
    user.avatar.save("avatar.webp", content, save=False)
    try:
        user.save(update_fields=["avatar"])
        membership = selectors.active_membership(user)
        if membership is not None:
            audit.record(organization=membership.organization, actor=user, action="user.avatar_set", target=user)
    except BaseException:
        if user.avatar.name:
            user.avatar.storage.delete(user.avatar.name)
        raise
    if old_name:
        _delete_file_after_commit(user.avatar, old_name)
    return user


@transaction.atomic
def remove_user_avatar(*, user: User) -> User:
    user = User.objects.select_for_update().get(pk=user.pk)
    old_name = user.avatar.name or ""
    if old_name:
        user.avatar.name = ""
        user.save(update_fields=["avatar"])
        membership = selectors.active_membership(user)
        if membership is not None:
            audit.record(organization=membership.organization, actor=user, action="user.avatar_removed", target=user)
        _delete_file_after_commit(user.avatar, old_name)
    return user


@transaction.atomic
def update_own_profile(*, user: User, first_name: str, last_name: str) -> User:
    """A user changes their own display name from their profile menu."""
    user.first_name = first_name
    user.last_name = last_name
    user.save(update_fields=["first_name", "last_name"])
    return user


@transaction.atomic
def change_own_password(*, user: User, old_password: str, new_password: str) -> User:
    """A user changes their own password; the old one proves it is really them (no email reset exists, D-123)."""
    if not user.check_password(old_password):
        raise ValidationError({"old_password": _("Mot de passe actuel incorrect.")})
    validate_password(new_password, user=user)
    user.set_password(new_password)
    user.save(update_fields=["password"])
    membership = selectors.active_membership(user)
    if membership is not None:
        audit.record(organization=membership.organization, actor=user, action="user.password_changed", target=user)
    return user


@transaction.atomic
def create_member(
    *,
    organization: Organization,
    actor: User | None,
    username: str,
    password: str,
    role: Role,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
) -> Membership:
    """The owner adds a new user with a role, and a password they will want to change (no email exists, D-123)."""
    validate_password(password)
    try:
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )
    except IntegrityError:
        raise ValidationError({"username": _("Cet identifiant existe déjà.")}) from None
    return add_member(organization=organization, user=user, role=role, actor=actor)


def _guard_last_owner(*, organization: Organization, membership: Membership) -> None:
    if membership.role == Role.OWNER and selectors.active_owner_count(organization) <= 1:
        raise ValidationError({"detail": _("Impossible : ce serait le dernier propriétaire actif.")})


@transaction.atomic
def set_member_role(
    *, organization: Organization, membership: Membership, actor: User | None, role: Role
) -> Membership:
    """Change a member's role. Refused when it would leave the organization without an active owner."""
    membership = Membership.objects.select_for_update().get(pk=membership.pk, organization=organization)
    if role != Role.OWNER:
        _guard_last_owner(organization=organization, membership=membership)
    before = {"role": membership.role}
    membership.role = role
    membership.save(update_fields=["role", "updated_at"])
    audit.record(
        organization=organization,
        actor=actor,
        action="membership.role_set",
        target=membership,
        before=before,
        after={"role": membership.role},
    )
    return membership


@transaction.atomic
def set_member_active(
    *, organization: Organization, membership: Membership, actor: User | None, is_active: bool
) -> Membership:
    """Deactivate (or reactivate) a member. Never a hard delete: other tables point to the user (D-123)."""
    membership = Membership.objects.select_for_update().get(pk=membership.pk, organization=organization)
    if not is_active:
        _guard_last_owner(organization=organization, membership=membership)
    before = {"is_active": membership.is_active}
    membership.is_active = is_active
    membership.save(update_fields=["is_active", "updated_at"])
    user = membership.user
    user.is_active = is_active
    user.save(update_fields=["is_active"])
    audit.record(
        organization=organization,
        actor=actor,
        action="membership.activated" if is_active else "membership.deactivated",
        target=membership,
        before=before,
        after={"is_active": is_active},
    )
    return membership


@transaction.atomic
def reset_member_password(
    *, organization: Organization, membership: Membership, actor: User | None, new_password: str
) -> Membership:
    """The owner types a new password for someone else (shown once); no email or SMS reset exists (D-123)."""
    membership = Membership.objects.select_for_update().get(pk=membership.pk, organization=organization)
    validate_password(new_password, user=membership.user)
    membership.user.set_password(new_password)
    membership.user.save(update_fields=["password"])
    audit.record(organization=organization, actor=actor, action="membership.password_reset", target=membership)
    return membership


@transaction.atomic
def record_job_run(*, job: Job, ok: bool, problems: int = 0) -> JobRun:
    """Keeps the last run of a scheduled job (P4-T04, D-140): the monitoring reads it, the next run replaces it."""
    run, _ = JobRun.objects.update_or_create(
        job=job, defaults={"ran_at": timezone.now(), "ok": ok, "problems": problems}
    )
    return run
