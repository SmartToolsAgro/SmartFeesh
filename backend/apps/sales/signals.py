"""A new organization starts with its first finance settings version (D-056); a truck load validated for
clients leaves a draft BL for each of them (D-160)."""

from typing import TYPE_CHECKING, Any

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.models import Organization, User
from apps.inventory import services as inventory

from . import services

if TYPE_CHECKING:
    from apps.inventory.models import Transfer


@receiver(post_save, sender=Organization, dispatch_uid="sales.first_finance_settings")
def give_first_finance_settings(
    sender: type[Organization], instance: Organization, created: bool, **kwargs: Any
) -> None:
    if created and not kwargs.get("raw", False):
        services.ensure_finance_settings(organization=instance)


@receiver(inventory.load_validated, dispatch_uid="sales.draft_delivery_notes_after_load")
def draft_delivery_notes_after_load(sender: Any, transfer: "Transfer", actor: User | None, **kwargs: Any) -> None:
    services.create_delivery_drafts(transfer=transfer, actor=actor)
