"""Audit trail: call `audit.record(...)` from a service, inside its transaction (ARCHITECTURE §4.9)."""

from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db import models

from .models import AuditLog, Organization, User


def record(
    *,
    organization: Organization,
    actor: User | None,
    action: str,
    target: models.Model | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditLog:
    """Write one audit entry.

    `action` is a dotted name such as "invoice.issued". `before` and `after` hold the values that changed;
    Decimals are stored as strings, so no precision is lost.
    """
    return AuditLog.objects.create(
        organization=organization,
        actor=actor,
        action=action,
        target_type=ContentType.objects.get_for_model(target) if target is not None else None,
        target_id=str(target.pk) if target is not None else "",
        target_repr=str(target)[:200] if target is not None else "",
        before=before,
        after=after,
    )
