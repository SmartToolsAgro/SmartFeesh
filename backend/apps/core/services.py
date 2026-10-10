"""Every write on core models goes through these functions (ARCHITECTURE §3)."""

from django.conf import settings
from django.db import transaction

from . import audit
from .models import Membership, Organization, Role, User


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
