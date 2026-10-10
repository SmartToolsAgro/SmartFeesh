"""Reusable read queries on core models."""

from .models import Membership, User


def active_membership(user: User) -> Membership | None:
    """The user's membership in an active organization. One organization exists today (ARCHITECTURE §4.6)."""
    return (
        Membership.objects.filter(user=user, is_active=True, organization__is_active=True)
        .select_related("organization")
        .order_by("id")
        .first()
    )
