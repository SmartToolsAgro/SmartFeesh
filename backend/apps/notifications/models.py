from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import OrganizationScopedModel


class Audience(models.TextChoices):
    # Every owner and manager of the organization.
    OFFICE = "office", _("Bureau")
    # One driver: `Notification.recipient`.
    DRIVER = "driver", _("Chauffeur")


class Notification(OrganizationScopedModel):
    """Something a driver did, told to the office, or something the office did for one driver, told to them (D-175).

    Written from the audit entry of the action, in the same transaction: a refused action tells nobody. The words
    are not stored: `kind` names the message and `params` holds its values as they were then, so each app shows
    it in the reader's language.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    audience = models.CharField(max_length=10, choices=Audience.choices)
    # The driver told, for the driver audience; empty for the office.
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # "day_sent", "load_validated"...: the message key in the apps (`notifications.kinds.<kind>`).
    kind = models.CharField(max_length=50)
    params = models.JSONField(default=dict)
    # Where a click goes, inside the app that shows it ("/journees", "/achats"...); empty: nowhere.
    link = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["organization", "audience", "-id"]),
            models.Index(fields=["recipient", "-id"]),
        ]

    def __str__(self) -> str:
        return f"{self.kind} · {self.audience}"


class NotificationRead(OrganizationScopedModel):
    """One reader has seen one notification: the office shares its notifications, each person reads them apart."""

    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["notification", "user"], name="one_read_per_notification_and_user"),
        ]
