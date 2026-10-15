"""The customer and supplier statement PDFs over chosen dates (D-156)."""

import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.boxes import selectors as boxes
from apps.boxes import services as box_services
from apps.boxes.models import BoxMovementKind
from apps.catalog.tests.factories import ProductFactory, ProductPriceFactory
from apps.core.models import Role
from apps.core.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.documents import rendering
from apps.documents import services as documents
from apps.inventory import services as stock
from apps.inventory.models import MovementKind
from apps.inventory.tests.factories import BatchFactory, StockLocationFactory
from apps.partners.tests.factories import CustomerFactory, SupplierFactory
from apps.purchasing import selectors as purchasing_selectors
from apps.purchasing import services as purchasing
from apps.reports import statements
from apps.sales import selectors as sales_selectors
from apps.sales import services as sales

pytestmark = pytest.mark.django_db

D = Decimal


@pytest.fixture(autouse=True)
def fake_pdf(monkeypatch):
    """Rendering needs Pango, which not every machine has: the HTML is kept and a stand-in PDF returned."""
    pages: list[str] = []

    def render(html: str) -> bytes:
        pages.append(html)
        return b"%PDF-1.7 fake"

    monkeypatch.setattr(rendering, "html_to_pdf", render)
    return pages


@pytest.fixture
def organization():
    return OrganizationFactory.create()


@pytest.fixture
def actor():
    return UserFactory.create()


@pytest.fixture
def today():
    return timezone.localdate()


@pytest.fixture
def counter(organization):
    return StockLocationFactory.create(organization=organization, name="Chambre froide 1", counter_sales=True)


@pytest.fixture
def crevette(organization, counter):
    product = ProductFactory.create(organization=organization, name="Crevette Royale", reference="CR-001")
    ProductPriceFactory.create(product=product, price=D("42.000"), valid_from=timezone.now() - dt.timedelta(days=300))
    batch = BatchFactory.create(
        organization=organization,
        product=product,
        unit_cost=D("20.000"),
        received_on=timezone.localdate() - dt.timedelta(days=120),
    )
    stock.post_movement(
        organization=organization,
        actor=None,
        kind=MovementKind.RECEIPT,
        batch=batch,
        quantity=D("500"),
        to_location=counter,
    )
    return product


@pytest.fixture
def customer(organization):
    return CustomerFactory.create(organization=organization, name="Restaurant Le Corail", payment_terms_days=30)


@pytest.fixture
def supplier(organization):
    return SupplierFactory.create(organization=organization, name="Mareyeur Port de Sfax")


def _days_ago(days: int) -> dt.datetime:
    return timezone.now() - dt.timedelta(days=days)


@pytest.fixture
def customer_story(organization, actor, customer, counter, crevette):
    """10 days ago 5 kg (210 DT); 8 days ago 6 small boxes left; 5 days ago a payment of 100; 2 days ago 3 kg
    (126 DT, 26 paid at the sale); yesterday 2 small boxes collected."""
    sales.create_sale(
        organization=organization,
        actor=actor,
        customer=customer,
        location=counter,
        lines=[{"product": crevette, "quantity": "5"}],
        sold_at=_days_ago(10),
        confirm=True,
    )
    room = box_services.holder_for(organization=organization, location=counter)
    client = box_services.holder_for(organization=organization, customer=customer)
    box_services.post_box_movement(
        organization=organization, actor=actor, kind=BoxMovementKind.OPENING, box_type="small", count=20, to_holder=room
    )
    box_services.post_box_movement(
        organization=organization,
        actor=actor,
        kind=BoxMovementKind.LEAVE,
        box_type="small",
        count=6,
        from_holder=room,
        to_holder=client,
        made_at=_days_ago(8),
    )
    sales.record_customer_payment(
        organization=organization,
        actor=actor,
        customer=customer,
        amount="100",
        method="cash",
        received_on=timezone.localdate() - dt.timedelta(days=5),
    )
    sales.create_sale(
        organization=organization,
        actor=actor,
        customer=customer,
        location=counter,
        lines=[{"product": crevette, "quantity": "3"}],
        sold_at=_days_ago(2),
        payment={"amount_paid": "26.000", "payment_method": "cash"},
        confirm=True,
    )
    box_services.post_box_movement(
        organization=organization,
        actor=actor,
        kind=BoxMovementKind.COLLECT,
        box_type="small",
        count=2,
        from_holder=client,
        to_holder=room,
        made_at=_days_ago(1),
    )


@pytest.fixture
def supplier_story(organization, actor, supplier, counter, crevette, today):
    """10 days ago 30 kg at 20 (600 DT) with 10 small boxes, invoiced 9 days ago; 3 days ago a payment of 250;
    yesterday 15 kg at 22 (330 DT), not invoiced."""
    first = purchasing.create_receipt(
        organization=organization,
        actor=actor,
        supplier=supplier,
        location=counter,
        received_on=today - dt.timedelta(days=10),
        lines=[{"product": crevette, "invoiced_quantity": "30", "accepted_quantity": "29.5", "unit_cost": "20"}],
        boxes={"small": 10},
    )
    purchasing.create_invoice(
        organization=organization,
        actor=actor,
        supplier=supplier,
        receipts=[first],
        invoice_date=today - dt.timedelta(days=9),
        due_date=today + dt.timedelta(days=20),
        post=True,
    )
    purchasing.record_payment(
        organization=organization,
        actor=actor,
        supplier=supplier,
        paid_on=today - dt.timedelta(days=3),
        amount="250",
        method="transfer",
        reference="VIR-77",
    )
    purchasing.create_receipt(
        organization=organization,
        actor=actor,
        supplier=supplier,
        location=counter,
        received_on=today - dt.timedelta(days=1),
        lines=[{"product": crevette, "invoiced_quantity": "15", "accepted_quantity": "15", "unit_cost": "22"}],
    )


# ---- customer ----


def test_a_customer_period_carries_the_balance_in_and_lists_only_its_own_days(
    organization, customer, customer_story, today
):
    statement = sales_selectors.customer_statement(
        organization, customer.pk, date_from=today - dt.timedelta(days=6), date_to=today
    )

    assert statement.opening_balance == D("210.000")
    assert [sale.number for sale in statement.sales] == [statement.sales[0].number]
    (sale,) = statement.sales
    assert [(line.product_name, line.quantity, line.unit_price, line.amount) for line in sale.lines] == [
        ("Crevette Royale", D("3.000"), D("42.000"), D("126.000"))
    ]
    assert [(payment.kind, payment.amount) for payment in statement.payments] == [
        ("payment", D("100.000")),
        ("on_spot", D("26.000")),
    ]
    assert statement.closing_balance == D("210.000")
    assert statement.entries[-1].balance == statement.closing_balance


def test_a_customer_up_to_a_day_starts_at_the_beginning(organization, customer, customer_story, today):
    statement = sales_selectors.customer_statement(
        organization, customer.pk, date_from=None, date_to=today - dt.timedelta(days=3)
    )

    assert statement.opening_balance == D("0.000")
    assert len(statement.sales) == 1
    assert [(payment.kind, payment.amount) for payment in statement.payments] == [("payment", D("100.000"))]
    assert statement.closing_balance == D("110.000")


def test_the_boxes_a_client_holds_before_during_and_after_the_period(organization, customer, customer_story, today):
    period = boxes.party_boxes(
        organization, customer_id=customer.pk, date_from=today - dt.timedelta(days=6), date_to=today
    )
    small = next(row for row in period.types if row.box_type == "small")
    assert (small.opening, small.added, small.removed, small.closing) == (6, 0, 2, 4)
    assert [(move.kind, move.count) for move in period.moves] == [("collect", -2)]

    before = boxes.party_boxes(
        organization, customer_id=customer.pk, date_from=None, date_to=today - dt.timedelta(days=3)
    )
    assert next(row for row in before.types if row.box_type == "small").closing == 6


def test_the_customer_pdf_shows_products_kilos_prices_payments_and_boxes(
    organization, customer, customer_story, today, fake_pdf
):
    document = statements.customer_statement_printable(
        organization, customer.pk, date_from=today - dt.timedelta(days=6), date_to=today
    )

    assert document.filename.startswith("releve-client-")
    assert documents.render_pdf(document, organization).startswith(b"%PDF")
    html = fake_pdf[-1]
    assert "Relevé client" in html
    assert "Crevette Royale" in html
    assert "3,000\u00a0kg" in html
    assert "126,000" in html
    assert "Payé à la vente" in html
    assert "le client nous doit" in html
    assert "Reprise chez client" in html


# ---- supplier ----


def test_a_supplier_statement_counts_invoices_and_payments_and_lists_receipts(
    organization, supplier, supplier_story, today
):
    statement = purchasing_selectors.supplier_statement(organization, supplier.pk, date_from=None, date_to=today)

    assert [receipt.total for receipt in statement.receipts] == [D("600.000"), D("330.000")]
    assert statement.receipts[0].invoice_number != ""
    assert statement.receipts[1].invoice_number == ""
    first_line = statement.receipts[0].lines[0]
    assert (first_line.invoiced_quantity, first_line.accepted_quantity, first_line.unit_cost) == (
        D("30.000"),
        D("29.500"),
        D("20.000"),
    )
    assert [(entry.kind, entry.amount, entry.balance) for entry in statement.entries] == [
        ("invoice", D("600.000"), D("600.000")),
        ("payment", D("-250.000"), D("350.000")),
    ]
    assert statement.closing_balance == D("350.000")
    assert statement.uninvoiced_total == D("330.000")


def test_a_supplier_period_carries_the_balance_in(organization, supplier, supplier_story, today):
    statement = purchasing_selectors.supplier_statement(
        organization, supplier.pk, date_from=today - dt.timedelta(days=5), date_to=today - dt.timedelta(days=2)
    )

    assert statement.opening_balance == D("600.000")
    assert statement.receipts == ()
    assert [payment.reference for payment in statement.payments] == ["VIR-77"]
    assert statement.closing_balance == D("350.000")


def test_the_boxes_we_owe_a_supplier(organization, supplier, supplier_story, today):
    figures = boxes.party_boxes(organization, supplier_id=supplier.pk, date_from=None, date_to=today)

    small = next(row for row in figures.types if row.box_type == "small")
    assert (small.added, small.removed, small.closing) == (10, 0, 10)


def test_the_supplier_pdf_shows_receipts_and_what_we_owe(organization, supplier, supplier_story, today, fake_pdf):
    documents.render_pdf(
        statements.supplier_statement_printable(organization, supplier.pk, date_from=None, date_to=today),
        organization,
    )

    html = fake_pdf[-1]
    assert "Relevé fournisseur" in html
    assert "29,500\u00a0kg" in html
    assert "nous devons" in html
    assert "Non facturé" in html
    assert "VIR-77" in html


# ---- API ----


def _client(organization, role):
    membership = MembershipFactory.create(organization=organization, role=role)
    client = APIClient()
    client.force_authenticate(membership.user)
    return client


def test_the_office_downloads_the_customer_pdf(organization, customer, customer_story, today):
    url = reverse("report-customer-statement", args=[customer.pk])

    response = _client(organization, Role.ACCOUNTANT).get(url, {"date_from": str(today - dt.timedelta(days=6))})

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert "releve-client-" in response["Content-Disposition"]


def test_the_office_downloads_the_supplier_pdf(organization, supplier, supplier_story):
    response = _client(organization, Role.MANAGER).get(reverse("report-supplier-statement", args=[supplier.pk]))

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"


def test_a_driver_may_not_read_a_statement(organization, customer):
    response = _client(organization, Role.DRIVER).get(reverse("report-customer-statement", args=[customer.pk]))

    assert response.status_code == 403


def test_another_companys_customer_or_supplier_is_not_found(organization):
    other = OrganizationFactory.create()
    client = _client(organization, Role.OWNER)

    assert (
        client.get(
            reverse("report-customer-statement", args=[CustomerFactory.create(organization=other).pk])
        ).status_code
        == 404
    )
    assert (
        client.get(
            reverse("report-supplier-statement", args=[SupplierFactory.create(organization=other).pk])
        ).status_code
        == 404
    )


def test_the_end_may_not_come_before_the_start(organization, customer):
    response = _client(organization, Role.OWNER).get(
        reverse("report-customer-statement", args=[customer.pk]), {"date_from": "2026-10-10", "date_to": "2026-10-01"}
    )

    assert response.status_code == 400


def test_the_real_renderer_makes_both_pdfs(
    organization, customer, supplier, customer_story, supplier_story, today, monkeypatch
):
    try:
        import weasyprint

        weasyprint.HTML(string="<p>test</p>").write_pdf()
    except OSError:  # Pango is not installed on this machine (CI and the Docker image have it)
        pytest.skip("WeasyPrint's native libraries are not available")
    monkeypatch.undo()
    for document in (
        statements.customer_statement_printable(organization, customer.pk, date_from=None, date_to=today),
        statements.supplier_statement_printable(organization, supplier.pk, date_from=None, date_to=today),
    ):
        pdf = documents.render_pdf(document, organization)

        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 2000
