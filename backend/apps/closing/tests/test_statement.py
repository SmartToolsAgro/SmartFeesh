"""The partner statement PDF (P6-T04, D-072): what the page says, when it is remade, who may ask."""

from decimal import Decimal

import pytest
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.urls import reverse

from apps.closing import services
from apps.core.models import Role
from apps.core.tests.factories import OrganizationFactory
from apps.documents import rendering
from apps.documents import services as documents
from apps.partnerships import selectors as partnerships

from .conftest import client_for, member, partnership, receive, sell

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture(autouse=True)
def storage(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture(autouse=True)
def commit_at_once(monkeypatch):
    monkeypatch.setattr(transaction, "on_commit", lambda func, using=None, robust=False: func())


@pytest.fixture(autouse=True)
def fake_renderer(monkeypatch):
    monkeypatch.setattr(rendering, "html_to_pdf", lambda html: b"%PDF-1.7 statement")


def statement(organization, batch):
    live = partnerships.live_partnership_of_batch(organization, batch_id=batch.pk)
    assert live is not None
    return live, documents.printable(organization, "partner_statement", live.pk)


def html_of(organization, batch):
    _live, printable = statement(organization, batch)
    return documents.render_html(printable)


def close(organization, actor, batch):
    return services.close_lot(organization=organization, actor=actor, batch_id=batch.pk, costs_confirmed=True)


def test_a_closed_profit_lot_is_explained_line_by_line(organization, actor, finished_lot, partner):
    close(organization, actor, finished_lot)

    html = html_of(organization, finished_lot)

    assert "Pêcherie Kerkennah" in html
    assert "Lot clôturé le" in html
    # The invoice's header and footer (D-131), with the partner where the invoice has the client.
    assert "Relevé du lot N° " in html
    assert "<th>Date</th><th>Partenaire</th>" in html
    assert 'class="page-footer"' in html
    assert "40 %" in html  # their profit rate
    assert "2 000,000" in html  # purchase cost of 100 kg at 20.000
    assert "32,500" in html  # a sale price
    assert "120,000" in html  # a typed cost
    assert "715,000" in html  # the net result
    assert "286,000" in html  # their 40 %
    assert "1 286,000" in html  # capital back + share
    assert "pas encore fait" in html  # not settled yet


def test_a_settled_lot_shows_the_payments(organization, actor, finished_lot, partner):
    close(organization, actor, finished_lot)
    services.settle_lot(
        organization=organization,
        actor=actor,
        batch_id=finished_lot.pk,
        payments=[{"amount": "1000.000", "method": "cash"}, {"amount": "286.000", "method": "transfer"}],
    )

    html = html_of(organization, finished_lot)

    assert "Total payé" in html
    assert "Espèces" in html
    assert "Virement" in html
    assert "pas encore fait" not in html


def test_an_open_lot_says_it_is_so_far(organization, actor, cold_room, partner):
    batch = receive(organization, cold_room, "50.000")
    partnership(organization, actor, batch, partner)
    sell(organization, actor, cold_room, batch, "10.000", "30.000")

    html = html_of(organization, batch)

    assert "CHIFFRES À CE JOUR" in html
    assert "300,000" in html
    assert "Reste en stock" in html


def test_a_loss_names_the_share_taken_from_the_capital(organization, actor, cold_room, partner):
    batch = receive(organization, cold_room, "100.000")
    partnership(organization, actor, batch, partner, capital="1000.000", loss="25")
    sell(organization, actor, cold_room, batch, "100.000", "15.000")  # 1 500 for a purchase of 2 000
    close(organization, actor, batch)

    html = html_of(organization, batch)

    assert "Le lot a perdu" in html
    assert "-500,000" in html
    assert "-125,000" in html  # 25 % of the loss
    assert "875,000" in html  # capital to return


def test_the_file_is_remade_when_the_lot_is_settled(organization, actor, finished_lot):
    close(organization, actor, finished_lot)
    live, before = statement(organization, finished_lot)
    services.settle_lot(
        organization=organization,
        actor=actor,
        batch_id=finished_lot.pk,
        payments=[{"amount": "1286.000", "method": "cash"}],
    )

    _same, after = statement(organization, finished_lot)

    assert before.version != after.version
    assert documents.printable(organization, "partner_statement", live.pk).version == after.version


def test_another_organization_cannot_print_it(organization, actor, finished_lot):
    live, _printable = statement(organization, finished_lot)

    with pytest.raises(ObjectDoesNotExist):
        documents.printable(OrganizationFactory.create(), "partner_statement", live.pk)


def test_the_api_serves_the_statement_to_the_office_only(organization, actor, finished_lot):
    live, _printable = statement(organization, finished_lot)
    url = reverse("document-pdf", args=["partner_statement", live.pk])

    assert client_for(member(organization, Role.OWNER)).get(url).status_code == 200
    assert client_for(member(organization, Role.ACCOUNTANT)).get(url).status_code == 200
    assert client_for(member(organization, Role.MANAGER)).get(url).status_code == 403
    assert client_for(member(organization, Role.DRIVER)).get(url).status_code == 403
