"""A new organization starts with the default expense categories (D-053)."""

from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.models import Organization

from . import services


@receiver(post_save, sender=Organization, dispatch_uid="expenses.default_categories")
def give_default_categories(sender: type[Organization], instance: Organization, created: bool, **kwargs: Any) -> None:
    if created and not kwargs.get("raw", False):
        services.ensure_default_categories(organization=instance)
