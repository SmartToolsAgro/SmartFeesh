import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Role
from apps.expenses.costing import add_months, first_of_month
from apps.inventory.tests.factories import StockLocationFactory

from .conftest import category, client_for, member
from .test_cold_room_cost import months, put

pytestmark = pytest.mark.django_db


def bill_payload(month, amount="500.000", **fields):
    return {"month": month.isoformat(), "amount": amount, **fields}


def test_a_bill_is_typed_approved_and_shows_in_the_month_view(api, cold_room):
    m0, m1, _m2, _m3 = months()

    created = api.post(reverse("electricity-bill-list"), bill_payload(m0), format="json")
    assert created.status_code == 201
    body = created.json()
    assert (body["status"], body["finalized"], body["amount"]) == ("draft", False, "500.000")

    month = api.get(reverse("cold-room-month"), {"month": m0.isoformat()}).json()
    assert month["estimated"] is True
    assert month["bill"]["id"] == body["id"]

    approved = api.post(reverse("electricity-bill-approve", args=[body["id"]]))
    assert (approved.status_code, approved.json()["finalized"], approved.json()["status"]) == (200, True, "approved")
    month = api.get(reverse("cold-room-month"), {"month": m0.isoformat()}).json()
    assert month["estimated"] is False
    assert month["total"] == "500.000"
    assert month["rooms"][0]["month_amount"] == "500.000"
    assert api.post(reverse("electricity-bill-list"), bill_payload(m0), format="json").status_code == 400

    estimated = api.get(reverse("cold-room-month"), {"month": m1.isoformat()}).json()
    assert estimated["estimated"] is True
    assert estimated["estimate_source_month"] == m0.isoformat()
    assert len(api.get(reverse("electricity-bill-list")).json()) == 1


def test_a_draft_bill_is_edited_and_deleted_and_the_month_must_be_over(api, cold_room):
    m0, *_ = months()
    this_month = first_of_month(timezone.localdate())
    assert api.post(reverse("electricity-bill-list"), bill_payload(this_month), format="json").status_code == 400

    bill = api.post(reverse("electricity-bill-list"), bill_payload(m0), format="json").json()
    edited = api.put(
        reverse("electricity-bill-detail", args=[bill["id"]]), bill_payload(m0, "610.500", payee="STEG"), format="json"
    )
    assert (edited.status_code, edited.json()["amount"], edited.json()["payee"]) == (200, "610.500", "STEG")
    assert api.delete(reverse("electricity-bill-detail", args=[bill["id"]])).status_code == 204
    assert api.get(reverse("electricity-bill-list")).json() == []


def test_weights_are_set_by_the_owner_only(organization, manager, cold_room):
    owner = member(organization, Role.OWNER)
    other = StockLocationFactory.create(organization=organization, name="Chambre -20")

    assert (
        client_for(manager)
        .put(reverse("cold-room-weight-detail", args=[other.pk]), {"weight": "2"}, format="json")
        .status_code
        == 403
    )
    answer = client_for(owner).put(reverse("cold-room-weight-detail", args=[other.pk]), {"weight": "2"}, format="json")
    assert answer.status_code == 200
    rows = {row["location_name"]: row for row in answer.json()}
    assert (rows["Chambre -20"]["weight"], rows["Chambre -20"]["share_percent"]) == ("2.000", "66.67")
    assert rows["Chambre froide 1"]["share_percent"] == "33.33"
    bad = client_for(owner).put(reverse("cold-room-weight-detail", args=[other.pk]), {"weight": "0"}, format="json")
    assert bad.status_code == 400
    assert client_for(manager).get(reverse("cold-room-weight-list")).status_code == 200


def test_the_accountant_reads_and_the_driver_is_refused(organization, cold_room):
    accountant = client_for(member(organization, Role.ACCOUNTANT))
    driver = client_for(member(organization, Role.DRIVER))
    assert accountant.get(reverse("electricity-bill-list")).status_code == 200
    assert (
        accountant.post(reverse("electricity-bill-list"), bill_payload(months()[0]), format="json").status_code == 403
    )
    assert driver.get(reverse("cold-room-month")).status_code == 403
    assert driver.get(reverse("recurring-cost-list")).status_code == 403


def test_the_lot_costs_endpoint_carries_the_cold_room_and_general_lines(api, organization, actor, cold_room):
    m0, m1, *_ = months()
    api.post(reverse("electricity-bill-list"), bill_payload(m0, "310.000", approve_now=True), format="json")
    lot = put(organization, "Dorade", "100", cold_room, m1)
    this_month = first_of_month(timezone.localdate())
    api.post(
        reverse("general-cost-list"),
        {
            "spent_on": this_month.isoformat(),
            "category": category(organization, "administration").pk,
            "amount": "260.000",
            "first_month": this_month.isoformat(),
            "months": 1,
            "description": "Assurance",
            "approve_now": True,
        },
        format="json",
    )

    costs = api.get(reverse("lot-costs"), {"batch": lot.pk}).json()
    kinds = {line["kind"] for line in costs["lines"]}
    assert kinds == {"cold_room", "general"}
    cold = [line for line in costs["lines"] if line["kind"] == "cold_room"]
    assert all(line["estimated"] and line["expense_id"] is None for line in cold[1:])
    assert cold[0]["location_name"] == "Chambre froide 1"
    assert float(costs["total"]) == pytest.approx(sum(float(line["amount"]) for line in costs["lines"]))

    api.post(reverse("electricity-bill-list"), bill_payload(m1, "620.000", approve_now=True), format="json")
    corrected = api.get(reverse("lot-costs"), {"batch": lot.pk}).json()
    adjustment = [line for line in corrected["lines"] if line["kind"] == "cold_room_adjustment"]
    assert len(adjustment) == 1
    assert adjustment[0]["spent_on"] == timezone.localdate().isoformat()


def test_recurring_costs_are_managed_by_the_owner_and_generate_the_month(organization, manager, cold_room):
    owner = client_for(member(organization, Role.OWNER))
    rent = category(organization, "rent")
    payload = {
        "name": "Loyer",
        "category": rent.pk,
        "monthly_amount": "1200.000",
        "start_month": add_months(first_of_month(timezone.localdate()), -1).isoformat(),
    }
    assert client_for(manager).post(reverse("recurring-cost-list"), payload, format="json").status_code == 403
    created = owner.post(reverse("recurring-cost-list"), payload, format="json")
    assert created.status_code == 201

    month = first_of_month(timezone.localdate()).isoformat()
    generated = client_for(manager).post(
        reverse("recurring-cost-generate"), {"month": month, "approve_now": True}, format="json"
    )
    assert generated.status_code == 200
    [period] = generated.json()
    assert (period["status"], period["amount"], period["months"]) == ("approved", "1200.000", 1)
    again = client_for(manager).post(reverse("recurring-cost-generate"), {"month": month}, format="json")
    assert again.json() == []

    stopped = owner.put(
        reverse("recurring-cost-detail", args=[created.json()["id"]]), {**payload, "is_active": False}, format="json"
    )
    assert stopped.json()["is_active"] is False
    assert owner.get(reverse("recurring-cost-list"), {"active_only": "true"}).json() == []
    listed = owner.get(reverse("general-cost-list"), {"month": month}).json()
    assert [row["description"] for row in listed] == ["Loyer"]


def test_a_general_cost_draft_is_deleted_and_not_edited_as_a_plain_expense(api, organization):
    this_month = first_of_month(timezone.localdate())
    draft = api.post(
        reverse("general-cost-list"),
        {
            "spent_on": timezone.localdate().isoformat(),
            "category": category(organization, "rent").pk,
            "amount": "90",
            "first_month": this_month.isoformat(),
            "months": 3,
        },
        format="json",
    )
    assert draft.status_code == 201
    expense_id = draft.json()["expense_id"]
    plain = api.put(
        reverse("expense-detail", args=[expense_id]),
        {
            "spent_on": timezone.localdate().isoformat(),
            "category": category(organization, "rent").pk,
            "amount": "1",
        },
        format="json",
    )
    assert plain.status_code == 400
    assert api.delete(reverse("general-cost-detail", args=[draft.json()["id"]])).status_code == 204
    assert api.get(reverse("expense-detail", args=[expense_id])).status_code == 404
