"""A load validated into a truck opens again the day its driver had sent that date (D-134)."""

from typing import TYPE_CHECKING, Any

from django.dispatch import receiver

from apps.core.models import User
from apps.inventory import services as inventory

from . import services

if TYPE_CHECKING:
    from apps.inventory.models import Transfer


@receiver(inventory.load_validated, dispatch_uid="dayclose.reopen_days_after_load")
def reopen_days_after_load(sender: Any, transfer: "Transfer", actor: User | None, **kwargs: Any) -> None:
    services.reopen_days_after_load(load=transfer, actor=actor)
