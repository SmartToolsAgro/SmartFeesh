"""Reusable read queries on core models."""

from django.db.models import QuerySet

from .models import Membership, Organization, Role, User

type MembershipQuerySet = QuerySet[Membership]


def active_membership(user: User) -> Membership | None:
    """The user's membership in an active organization. One organization exists today (ARCHITECTURE §4.6)."""
    return (
        Membership.objects.filter(user=user, is_active=True, organization__is_active=True)
        .select_related("organization", "user")
        .order_by("id")
        .first()
    )


def members_of(organization: Organization) -> MembershipQuerySet:
    """Every membership of one organization, active or not, with its user."""
    return Membership.objects.filter(organization=organization).select_related("user").order_by("user__username")


def active_owner_count(organization: Organization) -> int:
    """How many active owners the organization has (Paramètres > Users guards against losing the last one)."""
    return Membership.objects.filter(organization=organization, role=Role.OWNER, is_active=True).count()
