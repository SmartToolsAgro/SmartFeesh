"""A new organization starts with its first finance settings version (D-056)."""

from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.models import Organization

from . import services


@receiver(post_save, sender=Organization, dispatch_uid="sales.first_finance_settings")
def give_first_finance_settings(
    sender: type[Organization], instance: Organization, created: bool, **kwargs: Any
) -> None:
    if created and not kwargs.get("raw", False):
        services.ensure_finance_settings(organization=instance)
