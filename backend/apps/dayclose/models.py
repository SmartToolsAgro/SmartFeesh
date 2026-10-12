from typing import Any

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import OrganizationScopedModel, TimeStampedModel
from apps.core.money import MoneyField


class DayClosingStatus(models.TextChoices):
    # Sent by the driver, waiting for the office.
    SUBMITTED = "submitted", _("À vérifier")
    # The office asks the driver to explain; the driver sends it again with a note.
    JUSTIFICATION = "justification", _("Justification demandée")
    # Checked and locked: it never changes again.
    APPROVED = "approved", _("Approuvée")


class DayClosing(OrganizationScopedModel, TimeStampedModel):
    """The end of a driver's day (P3-T06, D-094): the cash the driver counted, next to what the day's records
    say it should be. The figures are kept as they were when the driver sent them."""

    # By name, not by import (ARCHITECTURE §3).
    driver_day = models.OneToOneField("fleet.DriverDay", on_delete=models.PROTECT, related_name="closing")
    status = models.CharField(max_length=20, choices=DayClosingStatus.choices, default=DayClosingStatus.SUBMITTED)
    # What the records say: opening cash + cash sales - cash expenses.
    expected_cash = MoneyField()
    counted_cash = MoneyField()
    # counted - expected, shown without judgement (negative: less cash than expected).
    difference = models.DecimalField(max_digits=14, decimal_places=3)
    driver_note = models.TextField(blank=True)
    # `selectors.day_summary` as it was when sent.
    summary: Any = models.JSONField(encoder=DjangoJSONEncoder)
    submitted_at = models.DateTimeField()
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-submitted_at", "-id"]

    def __str__(self) -> str:
        return f"{self.driver_day} · {self.get_status_display()}"
