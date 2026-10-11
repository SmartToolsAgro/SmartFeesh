"""Partnership lots and the partner's capital ledger (P6-T01, D-060)."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.closing.tests.conftest import client_for, member, partnership, receive, sell
from apps.core.models import AuditLog, Role
from apps.core.tests.factories import MembershipFactory
from apps.partners.tests.factories import SupplierFactory
from apps.partnerships import selectors, services
from apps.partnerships.models import CapitalEntry, CapitalEntryKind, PartnershipStatus

pytestmark = pytest.mark.django_db
D = Decimal


def entries(created) -> list[tuple[str, Decimal]]:
    return [(entry.kind, entry.amount) for entry in selectors.capital_entries_of(created)]


def errors_of(refused: pytest.ExceptionInfo[ValidationError]) -> dict[str, list[str]]:
    return refused.value.message_dict


def test_a_partnership_opens_the_partner_capital_ledger(organization, actor, cold_room, partner):
    batch = receive(organization, cold_room, "100.000")

    created = partnership(organization, actor, batch, partner, capital="5000.000", profit="40", loss="25")

    assert (created.status, created.profit_rate, created.loss_rate) == (
        PartnershipStatus.OPEN,
        D("40.00"),
        D("25.00"),
    )
    assert entries(created) == [(CapitalEntryKind.CONTRIBUTION, D("5000.000"))]
    assert selectors.capital_balance(created) == D("5000.000")
    assert AuditLog.objects.filter(action="partnership.created", target_id=str(created.pk)).exists()


def test_one_partner_per_lot_but_a_supplier_may_be_partner_in_several_lots(organization, actor, cold_room, partner):
    first = receive(organization, cold_room, "10.000", name="Dorade")
    second = receive(organization, cold_room, "10.000", name="Loup")
    partnership(organization, actor, first, partner)
    partnership(organization, actor, second, partner, capital="300.000", profit="35", loss="10")

    with pytest.raises(ValidationError) as refused:
        partnership(organization, actor, first, SupplierFactory.create(organization=organization))

    assert "un seul partenaire" in errors_of(refused)["batch"][0]
    assert selectors.partnerships_of(organization, partner_id=partner.pk).count() == 2


def test_a_partnership_is_set_before_the_first_sale_only(organization, actor, cold_room, partner):
    batch = receive(organization, cold_room, "10.000")
    sell(organization, actor, cold_room, batch, "1.000", "30.000")

    with pytest.raises(ValidationError) as refused:
        partnership(organization, actor, batch, partner)

    assert "avant la première vente" in errors_of(refused)["batch"][0]


def test_terms_are_checked_all_at_once(organization, actor, cold_room, partner):
    batch = receive(organization, cold_room, "10.000")
    partner.is_active = False
    partner.save()

    with pytest.raises(ValidationError) as refused:
        services.create_partnership(
            organization=organization,
            actor=actor,
            batch=batch,
            partner=partner,
            owner_capital="-1",
            partner_capital="10.0001",
            profit_rate="120",
            loss_rate="2.505",
        )

    assert set(errors_of(refused)) == {"partner", "owner_capital", "partner_capital", "profit_rate", "loss_rate"}


def test_changing_the_capital_posts_a_correction_never_an_edit(organization, actor, cold_room, partner):
    batch = receive(organization, cold_room, "10.000")
    created = partnership(organization, actor, batch, partner, capital="1000.000")

    services.update_partnership(partnership=created, actor=actor, partner_capital="750.000", profit_rate="45")

    created.refresh_from_db()
    assert (created.partner_capital, created.profit_rate) == (D("750.000"), D("45.00"))
    assert entries(created) == [
        (CapitalEntryKind.CONTRIBUTION, D("1000.000")),
        (CapitalEntryKind.CORRECTION, D("-250.000")),
    ]
    with pytest.raises(TypeError):
        CapitalEntry.objects.filter(partnership=created).update(amount=0)
    with pytest.raises(TypeError):
        CapitalEntry.objects.filter(partnership=created).delete()


def test_terms_are_fixed_once_the_lot_sold(organization, actor, cold_room, partner):
    batch = receive(organization, cold_room, "10.000")
    created = partnership(organization, actor, batch, partner)
    sell(organization, actor, cold_room, batch, "1.000", "30.000")

    with pytest.raises(ValidationError):
        services.update_partnership(partnership=created, actor=actor, profit_rate="50")
    with pytest.raises(ValidationError):
        services.cancel_partnership(partnership=created, actor=actor, reason="Erreur")


def test_cancelling_gives_the_capital_back_and_frees_the_lot(organization, actor, cold_room, partner):
    batch = receive(organization, cold_room, "10.000")
    created = partnership(organization, actor, batch, partner, capital="400.000")

    with pytest.raises(ValidationError):
        services.cancel_partnership(partnership=created, actor=actor, reason="")
    services.cancel_partnership(partnership=created, actor=actor, reason="Mauvais fournisseur")

    created.refresh_from_db()
    assert (created.status, created.cancel_reason) == (PartnershipStatus.CANCELLED, "Mauvais fournisseur")
    assert entries(created)[-1] == (CapitalEntryKind.RETURN, D("-400.000"))
    assert selectors.capital_balance(created) == D("0.000")
    assert selectors.live_partnership_of_batch(organization, batch_id=batch.pk) is None
    # The lot can take another partner.
    partnership(organization, actor, batch, SupplierFactory.create(organization=organization))


# ---- API ----


def test_the_owner_creates_lists_and_changes_a_partnership(api, organization, cold_room, partner):
    batch = receive(organization, cold_room, "20.000")

    created = api.post(
        "/api/v1/partnerships",
        {
            "batch": batch.pk,
            "partner": partner.pk,
            "owner_capital": "2000.000",
            "partner_capital": "1500.000",
            "profit_rate": "40",
            "loss_rate": "25",
        },
        format="json",
    )

    assert created.status_code == 201, created.json()
    data = created.json()
    assert (data["capital"], data["has_sold"], data["status"]) == ("1500.000", False, "open")
    assert data["capital_entries"][0]["kind"] == "contribution"
    listed = api.get("/api/v1/partnerships", {"batch": batch.pk}).json()
    assert listed["count"] == 1
    assert listed["results"][0]["partner"]["name"] == "Pêcherie Kerkennah"

    changed = api.patch(f"/api/v1/partnerships/{data['id']}", {"loss_rate": "30"}, format="json")
    assert changed.status_code == 200
    assert changed.json()["loss_rate"] == "30.00"

    bad = api.post(
        "/api/v1/partnerships",
        {
            "batch": batch.pk,
            "partner": 999999,
            "owner_capital": "",
            "partner_capital": "0",
            "profit_rate": "40",
            "loss_rate": "25",
        },
        format="json",
    )
    assert bad.status_code == 400
    assert "partner" in bad.json()

    cancelled = api.post(f"/api/v1/partnerships/{data['id']}/cancel", {"reason": "Erreur"}, format="json")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert api.get("/api/v1/partnerships").json()["count"] == 0
    assert api.get("/api/v1/partnerships", {"status": "cancelled"}).json()["count"] == 1


@pytest.mark.parametrize(
    ("role", "read", "write"),
    [(Role.ACCOUNTANT, 200, 403), (Role.MANAGER, 403, 403), (Role.DRIVER, 403, 403)],
)
def test_only_the_owner_writes_partnerships(organization, cold_room, partner, role, read, write):
    batch = receive(organization, cold_room, "20.000")
    client = client_for(member(organization, role))

    assert client.get("/api/v1/partnerships").status_code == read
    body = {
        "batch": batch.pk,
        "partner": partner.pk,
        "owner_capital": "0",
        "partner_capital": "0",
        "profit_rate": "40",
        "loss_rate": "25",
    }
    assert client.post("/api/v1/partnerships", body, format="json").status_code == write


def test_another_organization_sees_nothing(organization, actor, cold_room, partner):
    created = partnership(organization, actor, receive(organization, cold_room, "5.000"), partner)
    stranger = client_for(MembershipFactory.create(role=Role.OWNER))

    assert stranger.get(f"/api/v1/partnerships/{created.pk}").status_code == 404
    assert stranger.get("/api/v1/partnerships").json()["count"] == 0
