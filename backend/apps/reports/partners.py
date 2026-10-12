"""Partnership report (P7-T05, D-117): per partner, what they put in, got back and still have in the company,
and what they earned, were paid and are still owed. Read-only.

The period flows come from the partners' two ledgers (`partnerships.partner_flows`); the amounts still open are
the balances the screens show (`capital_by_partner`, `profit_share_balance_of_partner`), as of today. Capital,
profit share and trade payable are three separate balances (D-031, D-040) and are never added together.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from apps.core.models import Organization
from apps.partners import selectors as partners
from apps.partnerships import selectors as partnerships

ZERO = Decimal("0.000")


@dataclass(frozen=True)
class PartnerLine:
    partner_id: int
    name: str
    lots: int
    # Capital, over the period
    contributed: Decimal
    loss_deducted: Decimal
    returned: Decimal
    # Capital still in the company now
    capital_outstanding: Decimal
    # Profit share, over the period
    share: Decimal
    uncovered_loss: Decimal
    late_adjustments: Decimal
    paid: Decimal
    # Profit share still owed to the partner (+) or by them (-) now
    share_due: Decimal


@dataclass(frozen=True)
class PartnerReport:
    date_from: dt.date
    date_to: dt.date
    rows: list[PartnerLine]
    totals: PartnerLine


def _total(rows: list[PartnerLine], field: str) -> Decimal:
    return sum((getattr(row, field) for row in rows), ZERO)


def partner_report(organization: Organization, *, date_from: dt.date, date_to: dt.date) -> PartnerReport:
    """Every partner with a movement in the period or something still open, biggest capital first."""
    flows = partnerships.partner_flows(organization, date_from=date_from, date_to=date_to)
    capital = partnerships.capital_by_partner(organization)
    names = {supplier.pk: supplier.name for supplier in partners.suppliers_of(organization, status="all")}
    rows: list[PartnerLine] = []
    for partner_id in sorted(set(flows) | set(capital)):
        flow = flows.get(partner_id, partnerships.PartnerFlows(partner_id))
        held = capital.get(partner_id)
        due = partnerships.profit_share_balance_of_partner(organization, partner_id=partner_id)
        outstanding = held.capital if held is not None else ZERO
        rows.append(
            PartnerLine(
                partner_id=partner_id,
                name=names.get(partner_id, "?"),
                lots=held.lots if held is not None else 0,
                contributed=flow.contributed,
                loss_deducted=flow.loss_deducted,
                returned=flow.returned,
                capital_outstanding=outstanding,
                share=flow.share,
                uncovered_loss=flow.uncovered_loss,
                late_adjustments=flow.late_adjustments,
                paid=flow.paid,
                share_due=due,
            )
        )
    rows.sort(key=lambda r: (-r.capital_outstanding, r.name))
    totals = PartnerLine(
        partner_id=0,
        name="",
        lots=sum(r.lots for r in rows),
        contributed=_total(rows, "contributed"),
        loss_deducted=_total(rows, "loss_deducted"),
        returned=_total(rows, "returned"),
        capital_outstanding=_total(rows, "capital_outstanding"),
        share=_total(rows, "share"),
        uncovered_loss=_total(rows, "uncovered_loss"),
        late_adjustments=_total(rows, "late_adjustments"),
        paid=_total(rows, "paid"),
        share_due=_total(rows, "share_due"),
    )
    return PartnerReport(date_from, date_to, rows, totals)
