"""Every audited action is checked against `rules.RULES` and may tell the office or a driver (D-175)."""

import logging
from typing import Any

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.models import AuditLog

from . import rules

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AuditLog, dispatch_uid="notifications.from_audit")
def notify_from_audit(sender: Any, instance: AuditLog, created: bool, **kwargs: Any) -> None:
    if not created or instance.action not in rules.RULES:
        return
    # In the action's own transaction, so a refused action tells nobody; but a notification that cannot be
    # written never refuses the action: its savepoint is rolled back alone.
    try:
        with transaction.atomic():
            rules.apply(instance)
    except Exception:
        logger.exception("No notification for %s %s", instance.action, instance.target_id)
