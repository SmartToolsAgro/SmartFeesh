"""Demo supplier invoice and payment: the port wholesaler's invoice for this morning's receipt, partly paid.

FF-0001 charges receipt BR-0001 (dorade 62 kg invoiced × 20.250 + rouget 20 kg × 10.800 = 1 471.500 DT),
posted, due in 15 days; RF-0001 pays 500 DT of it by cheque. The supplier balance is then 971.500 DT.
Known by the supplier's invoice number, so the seed adds them only once.
"""

import datetime as dt

from django.utils import timezone

from apps.core.models import Organization, User
from apps.partners import selectors as partners
from apps.purchasing import selectors, services
from apps.purchasing.services import PaymentMethod

from .receipts import DELIVERY_NOTE, SUPPLIER

SUPPLIER_INVOICE = "MPS-F-2026-118"
PAID = "500.000"
CHEQUE = "CH-0042117"


def seed_supplier_invoices(*, organization: Organization, actor: User | None) -> int:
    """Record the demo invoice and its payment when they are not there yet. Returns how many invoices were made."""
    if selectors.invoices_of(organization, search=SUPPLIER_INVOICE).exists():
        return 0
    receipt = selectors.receipts_of(organization, search=DELIVERY_NOTE, uninvoiced=True).first()
    if receipt is None:
        return 0
    supplier = partners.suppliers_of(organization, status="all").get(reference=SUPPLIER)
    today = timezone.localdate()
    invoice = services.create_invoice(
        organization=organization,
        actor=actor,
        supplier=supplier,
        receipts=[receipt],
        invoice_date=today,
        due_date=today + dt.timedelta(days=15),
        supplier_reference=SUPPLIER_INVOICE,
        post=True,
    )
    services.record_payment(
        organization=organization,
        actor=actor,
        supplier=supplier,
        paid_on=today,
        amount=PAID,
        method=PaymentMethod.CHEQUE,
        reference=CHEQUE,
        allocations=[{"invoice": invoice, "amount": PAID}],
    )
    return 1
