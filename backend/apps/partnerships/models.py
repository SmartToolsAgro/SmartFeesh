from typing import Any

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import OrganizationScopedModel, OrganizationScopedQuerySet, TimeStampedModel
from apps.core.money import MoneyField

# ---- Partnership lots (P6-T01, D-060) ----


class PartnershipStatus(models.TextChoices):
    # The lot is still being sold: its result is live ("so far").
    OPEN = "open", _("En cours")
    # The lot is closed and its result frozen (P6-T02): capital back ± share is known.
    CLOSED = "closed", _("Clôturé")
    # The partner got their capital back ± share (P6-T03).
    SETTLED = "settled", _("Réglé")
    # Removed before the lot's first sale: the capital went back, nothing was shared.
    CANCELLED = "cancelled", _("Annulé")


class LotPartnership(OrganizationScopedModel, TimeStampedModel):
    """A lot bought together by the owner and one partner supplier (client meeting §5, D-040, D-060).

    Each side puts money in. When the lot closes, the partner gets their profit % of the net profit, or
    carries their loss % of the loss, deducted from their capital (Q3, D-031). One live partnership per
    lot; a supplier can be a partner in several lots at once, each with its own capital and rates (Q22).
    The terms change only before the lot's first sale; then they are what the result uses.
    """

    # By name, not by import (ARCHITECTURE §3): read through `inventory.selectors` and `partners.selectors`.
    batch = models.ForeignKey("inventory.Batch", on_delete=models.PROTECT, related_name="+")
    partner = models.ForeignKey("partners.Supplier", on_delete=models.PROTECT, related_name="+")
    # What each side put into the lot. The partner's is also the first entry of their capital ledger.
    owner_capital = MoneyField()
    partner_capital = MoneyField()
    # Percent with 2 decimals: the partner's share of a profit, and of a loss (two rates, D-031).
    profit_rate = models.DecimalField(max_digits=5, decimal_places=2)
    loss_rate = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.CharField(max_length=20, choices=PartnershipStatus.choices, default=PartnershipStatus.OPEN)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    cancel_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["batch"],
                condition=~models.Q(status="cancelled"),
                name="one_live_partnership_per_lot",
            ),
            models.CheckConstraint(
                condition=models.Q(owner_capital__gte=0) & models.Q(partner_capital__gte=0),
                name="partnership_capital_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(profit_rate__gte=0)
                & models.Q(profit_rate__lte=100)
                & models.Q(loss_rate__gte=0)
                & models.Q(loss_rate__lte=100),
                name="partnership_rates_are_percents",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.batch} · {self.partner}"


# ---- The partner's capital, a ledger per partner and lot ----


class CapitalEntryKind(models.TextChoices):
    # Money the partner put into the lot (+).
    CONTRIBUTION = "contribution", _("Apport")
    # The amount put in was corrected before the first sale (+ or −).
    CORRECTION = "correction", _("Correction de l'apport")
    # Their loss share taken from their capital when the lot closed at a loss (−, D-031).
    LOSS_DEDUCTION = "loss_deduction", _("Part de perte déduite")
    # A reopened lot gives the deducted loss share back (+): the next closing deducts it again.
    LOSS_REVERSAL = "loss_reversal", _("Annulation de la déduction")
    # Capital paid back to the partner (−): at settlement (P6-T03) or when a partnership is cancelled.
    RETURN = "return", _("Remboursement")


class CapitalEntryQuerySet(OrganizationScopedQuerySet["CapitalEntry"]):
    def update(self, **kwargs: Any) -> int:
        raise TypeError("Capital entries are append-only: post a correcting entry instead")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise TypeError("Capital entries are append-only: they are never deleted")


class CapitalEntry(OrganizationScopedModel):
    """One change of a partner's capital in one lot (D-060). Signed: + puts money in, − takes it out.

    The capital is a balance of its own: never mixed with what the company owes the supplier for goods
    (D-043) nor with their profit share (D-031). Append-only, like the stock ledger.
    """

    partnership = models.ForeignKey(LotPartnership, on_delete=models.PROTECT, related_name="capital_entries")
    kind = models.CharField(max_length=20, choices=CapitalEntryKind.choices)
    amount = MoneyField()
    entry_date = models.DateField()
    note = models.CharField(max_length=300, blank=True)
    # The frozen lot result that caused it (a loss deduction or its reversal), by id: `closing` reads us.
    lot_result_id = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    objects = CapitalEntryQuerySet.as_manager()  # type: ignore[misc]

    class Meta:
        ordering = ["entry_date", "id"]
        verbose_name_plural = "capital entries"

    def __str__(self) -> str:
        return f"{self.partnership} · {self.kind} · {self.amount}"
