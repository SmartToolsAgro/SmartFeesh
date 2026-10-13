"""The end of a driver's day (P3-T06, D-094): the summary, the counted cash and the office review."""

import datetime as dt
from decimal import Decimal
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.tests.factories import ProductFactory, ProductPriceFactory
from apps.core.models import Role
from apps.core.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.fleet import services as fleet
from apps.inventory import services as inventory
from apps.inventory.models import MovementKind
from apps.inventory.tests.factories import BatchFactory, StockLocationFactory
from apps.partners import services as partners

pytestmark = pytest.mark.django_db


def client_for(membership):
    client = APIClient()
    client.force_authenticate(membership.user)
    return client


@pytest.fixture
def day():
    """A driver with a loaded truck: 12 kg of dorade at 28 DT, 50 DT in the till, day started."""
    organization = OrganizationFactory.create()
    actor = UserFactory.create()
    driver = MembershipFactory.create(organization=organization, role=Role.DRIVER)
    office = MembershipFactory.create(organization=organization, role=Role.MANAGER)
    room = StockLocationFactory.create(organization=organization, name="Chambre froide 1")
    truck = fleet.create_truck(
        organization=organization, actor=actor, name="Camion 1", plate="101 TU 2001", driver=driver.user
    )
    product = ProductFactory.create(organization=organization, name="Dorade royale", reference="DO-003")
    ProductPriceFactory.create(
        product=product, price=Decimal("28.000"), valid_from=timezone.now() - dt.timedelta(days=3)
    )
    batch = BatchFactory.create(organization=organization, product=product, received_on=timezone.localdate())
    inventory.post_movement(
        organization=organization,
        actor=None,
        kind=MovementKind.RECEIPT,
        batch=batch,
        quantity="20",
        to_location=room,
    )
    inventory.create_transfer(
        organization=organization,
        actor=actor,
        from_location=room,
        to_location=truck.location,
        transferred_on=timezone.localdate(),
        lines=[{"product": product, "quantity": Decimal("12")}],
        validate=True,
    )
    customer = partners.create_customer(
        organization=organization, actor=actor, name="Restaurant Le Port", credit_limit=Decimal("500.000")
    )
    api = client_for(driver)
    assert api.post(reverse("my-day"), {"opening_cash": "50"}, format="json").status_code == 201
    owner = MembershipFactory.create(organization=organization, role=Role.OWNER)
    return {
        "api": api,
        "office": client_for(office),
        "owner": client_for(owner),
        "organization": organization,
        "product": product,
        "room": room,
        "batch": batch,
        "truck": truck,
        "customer": customer,
    }


def sell(day, kg, paid):
    return day["api"].post(
        reverse("sale-list"),
        {
            "customer": day["customer"].pk,
            "location": day["truck"].location_id,
            "confirm_now": True,
            "amount_paid": paid,
            "payment_method": "cash",
            "lines": [{"product": day["product"].pk, "quantity": kg}],
        },
        format="json",
    )


def test_the_summary_adds_up_the_day(day):
    assert sell(day, "5", "100.000").status_code == 201  # 140 DT, 40 on credit

    summary = day["api"].get(reverse("my-day-summary")).json()["summary"]

    assert (summary["sales_count"], summary["sales_total"], summary["cash_received"], summary["on_credit"]) == (
        1,
        "140.000",
        "100.000",
        "40.000",
    )
    assert summary["expected_cash"] == "150.000"  # 50 at the start + 100 received
    assert summary["products"][0] | {"product_id": 0} == {
        "product_id": 0,
        "product_name": "Dorade royale",
        "opening": "0.000",
        "loaded": "12.000",
        "sold": "5.000",
        "lost": "0.000",
        "returned": "0.000",
        "remaining": "7.000",
        "unexplained": "0.000",
    }


def test_kilos_left_on_the_truck_from_an_earlier_day_are_its_opening_stock(day):
    """Bug of 2026-10-13: a truck sold more than it was loaded that day (Crevette 109 sold, 100 loaded).
    The 2 kg of dorade sold today were on the truck since yesterday: they are the opening stock, so the
    day adds up: opening + loaded - returned - sold - lost = left."""
    yesterday = timezone.localdate() - dt.timedelta(days=1)
    left_over = BatchFactory.create(organization=day["organization"], product=day["product"], received_on=yesterday)
    inventory.post_movement(
        organization=day["organization"],
        actor=None,
        kind=MovementKind.RECEIPT,
        batch=left_over,
        quantity="2",
        to_location=day["room"],
        occurred_at=timezone.make_aware(dt.datetime.combine(yesterday, dt.time(9, 0))),
    )
    inventory.create_transfer(
        organization=day["organization"],
        actor=None,
        from_location=day["room"],
        to_location=day["truck"].location,
        transferred_on=yesterday,
        lines=[{"product": day["product"], "quantity": Decimal("2")}],
        validate=True,
    )
    assert sell(day, "13", "100.000").status_code == 201

    product = day["api"].get(reverse("my-day-summary")).json()["summary"]["products"][0]

    assert (product["opening"], product["loaded"], product["sold"], product["remaining"]) == (
        "2.000",
        "12.000",
        "13.000",
        "1.000",
    )
    assert product["unexplained"] == "0.000"


def test_stock_that_left_the_truck_without_a_record_is_unexplained(day):
    """Kilos that leave the truck by a hand adjustment, with no sale, loss or transfer behind them, show as a gap."""
    sell(day, "3", "84.000")
    inventory.post_movement(
        organization=day["organization"],
        actor=None,
        kind=MovementKind.ADJUSTMENT,
        batch=day["batch"],
        quantity="2",
        from_location=day["truck"].location,
        reason="Test",
    )

    product = day["api"].get(reverse("my-day-summary")).json()["summary"]["products"][0]

    assert (product["loaded"], product["sold"], product["remaining"]) == ("12.000", "3.000", "7.000")
    assert product["unexplained"] == "-2.000"


def test_the_driver_sends_the_day_and_the_office_approves_it_after_a_justification(day):
    sell(day, "5", "100.000")

    sent = day["api"].post(
        reverse("my-day-closing"), {"counted_cash": "140.000", "note": "Un billet de 10 manque"}, format="json"
    )
    again = day["api"].post(reverse("my-day-closing"), {"counted_cash": "150.000"}, format="json")

    assert sent.status_code == 201
    assert sent.json()["closing"]["status"] == "submitted"
    assert again.status_code == 400  # already sent
    closing = day["office"].get(reverse("day-closing-list")).json()[0]
    assert (closing["expected_cash"], closing["counted_cash"], closing["difference"]) == (
        "150.000",
        "140.000",
        "-10.000",
    )
    detail = day["office"].get(reverse("day-closing-detail", args=[closing["id"]])).json()
    assert detail["driver_note"] == "Un billet de 10 manque"
    assert detail["summary"]["sales_total"] == "140.000"

    asked = day["office"].post(
        reverse("day-closing-justification", args=[closing["id"]]), {"reason": "Expliquez la différence"}, format="json"
    )
    assert asked.json()["status"] == "justification"
    resent = day["api"].post(
        reverse("my-day-closing"), {"counted_cash": "140.000", "note": "Dépense non saisie"}, format="json"
    )
    assert resent.status_code == 201
    approved = day["office"].post(reverse("day-closing-approve", args=[closing["id"]]))
    assert approved.json()["status"] == "approved"
    assert day["api"].post(reverse("my-day-closing"), {"counted_cash": "1"}, format="json").status_code == 400  # locked
    assert day["office"].post(reverse("day-closing-approve", args=[closing["id"]])).status_code == 400


def test_only_the_right_people_use_the_screens(day):
    assert day["office"].get(reverse("my-day-summary")).status_code == 403
    assert day["api"].get(reverse("day-closing-list")).status_code == 403
    assert client_for(MembershipFactory.create(role=Role.DRIVER)).get(reverse("my-day-summary")).status_code == 404


def test_an_approved_day_is_closed_to_sales_expenses_and_losses(day):
    sell(day, "1", "28.000")
    day["api"].post(reverse("my-day-closing"), {"counted_cash": "78.000"}, format="json")
    closing = day["office"].get(reverse("day-closing-list")).json()[0]

    day["office"].post(reverse("day-closing-approve", args=[closing["id"]]))

    assert sell(day, "1", "28.000").status_code == 403
    expense = day["api"].post(reverse("my-expenses"), {"category": 1, "amount": "5"}, format="multipart")
    loss = day["api"].post(
        reverse("my-losses"),
        {"product": day["product"].pk, "quantity": "1", "reason": "spoiled"},
        format="multipart",
    )
    assert (expense.status_code, loss.status_code) == (403, 403)
    assert day["api"].post(reverse("my-return")).status_code == 403


def test_a_sale_sent_again_after_the_day_is_approved_is_answered_not_refused(day):
    """The phone sent a sale, lost the answer, and the office approved the day meanwhile: the retry gets the
    recorded sale back (201, once), it is not refused as a new sale on a closed day."""
    from apps.sales.models import Sale

    client_uuid = str(uuid4())
    body = {
        "customer": day["customer"].pk,
        "location": day["truck"].location_id,
        "confirm_now": True,
        "client_uuid": client_uuid,
        "amount_paid": "28.000",
        "payment_method": "cash",
        "lines": [{"product": day["product"].pk, "quantity": "1"}],
    }
    first = day["api"].post(reverse("sale-list"), body, format="json")
    assert first.status_code == 201
    day["api"].post(reverse("my-day-closing"), {"counted_cash": "78.000"}, format="json")
    closing = day["office"].get(reverse("day-closing-list")).json()[0]
    day["office"].post(reverse("day-closing-approve", args=[closing["id"]]))

    retry = day["api"].post(reverse("sale-list"), body, format="json")

    assert (retry.status_code, retry.json()["id"]) == (201, first.json()["id"])
    assert Sale.objects.filter(client_uuid=client_uuid).count() == 1
    assert sell(day, "1", "28.000").status_code == 403  # a new sale on the approved day is still refused


def test_customers_sold_to_lately_come_first(day):
    other = partners.create_customer(organization=day["customer"].organization, actor=None, name="Aaa Hôtel")

    names = [c["name"] for c in day["api"].get(reverse("my-customers")).json()]
    assert names == ["Aaa Hôtel", "Restaurant Le Port"]  # alphabetical before any sale

    sell(day, "1", "28.000")
    names = [c["name"] for c in day["api"].get(reverse("my-customers")).json()]
    assert names == ["Restaurant Le Port", "Aaa Hôtel"]
    assert other.pk


def test_a_refused_send_is_reported_once_and_the_office_marks_it_dealt_with(day):
    body = {
        "kind": "sale",
        "what": "Restaurant Le Port",
        "reason": "Limite de crédit dépassée",
        "client_uuid": str(uuid4()),
    }

    first = day["api"].post(reverse("my-sync-problems"), body, format="json")
    again = day["api"].post(reverse("my-sync-problems"), body, format="json")

    assert first.status_code == 201
    assert again.json()["id"] == first.json()["id"]
    listed = day["office"].get(reverse("sync-problem-list")).json()
    assert [(p["kind"], p["label"], p["reason"]) for p in listed] == [
        ("sale", "Restaurant Le Port", "Limite de crédit dépassée")
    ]
    assert day["office"].post(reverse("sync-problem-resolve", args=[first.json()["id"]])).json()["resolved_at"]
    assert day["office"].get(reverse("sync-problem-list")).json() == []
    assert day["api"].get(reverse("sync-problem-list")).status_code == 403
    assert day["office"].post(reverse("my-sync-problems"), body, format="json").status_code == 403


def test_a_cash_difference_nobody_explained_is_an_alert(day):
    from apps.dayclose import selectors

    sell(day, "5", "100.000")  # expected cash: 50 + 100 = 150
    day["api"].post(reverse("my-day-closing"), {"counted_cash": "140.000"}, format="json")
    organization = day["truck"].organization

    rows = selectors.unexplained_cash_differences(organization)
    assert [(row.difference, row.day) for row in rows] == [(Decimal("-10.000"), timezone.localdate())]
    dashboard = day["owner"].get(reverse("dashboard")).json()
    assert dashboard["cash_difference_count"] == 1
    assert dashboard["cash_differences"][0]["difference"] == "-10.000"


def test_an_explained_or_exact_day_is_not_an_alert(day):
    from apps.dayclose import selectors

    sell(day, "5", "100.000")
    day["api"].post(
        reverse("my-day-closing"), {"counted_cash": "140.000", "note": "Un billet de 10 manque"}, format="json"
    )
    assert selectors.unexplained_cash_differences(day["truck"].organization) == []


def test_a_payment_collected_by_the_driver_counts_in_the_day_cash_and_is_recorded_once(day):
    sell(day, "5", "100.000")  # 140 DT, 40 left on credit
    owed = {c["name"]: c["owes"] for c in day["api"].get(reverse("my-customers")).json()}
    assert owed["Restaurant Le Port"] == "40.000"
    body = {"customer": day["customer"].pk, "amount": "30.000", "method": "cash", "client_uuid": str(uuid4())}

    first = day["api"].post(reverse("my-payments"), body, format="json")
    again = day["api"].post(reverse("my-payments"), body, format="json")

    assert first.status_code == 201
    assert again.json()["id"] == first.json()["id"]
    assert [p["amount"] for p in day["api"].get(reverse("my-payments")).json()] == ["30.000"]
    owed = {c["name"]: c["owes"] for c in day["api"].get(reverse("my-customers")).json()}
    assert owed["Restaurant Le Port"] == "10.000"
    summary = day["api"].get(reverse("my-day-summary")).json()["summary"]
    assert (summary["payments_cash"], summary["expected_cash"]) == ("30.000", "180.000")  # 50 + 100 + 30
    assert (
        day["api"].post(reverse("my-payments"), {**body, "amount": "0", "client_uuid": None}, format="json").status_code
        == 400
    )
    assert day["office"].post(reverse("my-payments"), body, format="json").status_code == 403


def test_an_approved_day_refuses_new_customer_payments(day):
    day["api"].post(reverse("my-day-closing"), {"counted_cash": "50.000"}, format="json")
    closing = day["office"].get(reverse("day-closing-list")).json()[0]
    day["office"].post(reverse("day-closing-approve", args=[closing["id"]]))

    body = {"customer": day["customer"].pk, "amount": "5.000", "method": "cash"}

    assert day["api"].post(reverse("my-payments"), body, format="json").status_code == 403


# ---- Several days on one date and the history (D-134) ----


def test_a_sent_day_is_closed_and_the_driver_starts_another_one_the_same_date(day):
    sell(day, "5", "100.000")
    day["api"].post(reverse("my-day-closing"), {"counted_cash": "150.000"}, format="json")

    assert sell(day, "1", "28.000").status_code == 403  # sent: nothing more on it
    assert day["api"].get(reverse("my-day")).json()["ended_at"] is not None

    second = day["api"].post(reverse("my-day"), {"opening_cash": "20"}, format="json")
    assert second.status_code == 201
    assert second.json()["number"] == 2
    # Asking again while it runs changes nothing.
    assert day["api"].post(reverse("my-day"), {"opening_cash": "99"}, format="json").json()["id"] == second.json()["id"]
    assert sell(day, "2", "56.000").status_code == 201

    summary = day["api"].get(reverse("my-day-summary")).json()["summary"]
    # Only this day's sale and cash; the morning's load belongs to the first day.
    assert (summary["sales_count"], summary["sales_total"], summary["expected_cash"]) == (1, "56.000", "76.000")
    assert summary["products"][0]["loaded"] == "0.000"
    assert summary["products"][0]["sold"] == "2.000"

    sent = day["api"].post(reverse("my-day-closing"), {"counted_cash": "76.000"}, format="json")
    assert sent.status_code == 201
    rows = day["office"].get(reverse("day-closing-list"), {"status": "submitted"}).json()
    assert [(row["number"], row["expected_cash"]) for row in rows] == [(2, "76.000"), (1, "150.000")]


def test_the_driver_sees_the_history_and_sends_a_justification_from_it(day):
    sell(day, "5", "100.000")
    day["api"].post(reverse("my-day-closing"), {"counted_cash": "140.000"}, format="json")
    first = day["api"].get(reverse("my-day-list")).json()[0]
    day["api"].post(reverse("my-day"), {"opening_cash": "0"}, format="json")
    sell(day, "1", "28.000")  # on the second day: the first one's figures do not move
    closing_id = day["office"].get(reverse("day-closing-list")).json()[0]["id"]
    day["office"].post(
        reverse("day-closing-justification", args=[closing_id]), {"reason": "Il manque 10 DT"}, format="json"
    )

    history = day["api"].get(reverse("my-day-list")).json()
    assert [(row["number"], row["closing"] and row["closing"]["status"]) for row in history] == [
        (2, None),
        (1, "justification"),
    ]
    assert history[1]["closing"]["difference"] == "-10.000"
    detail = day["api"].get(reverse("my-day-detail", args=[first["id"]])).json()
    assert (detail["summary"]["sales_total"], detail["summary"]["products"][0]["remaining"]) == ("140.000", "7.000")

    resent = day["api"].post(
        reverse("my-past-day-closing", args=[first["id"]]),
        {"counted_cash": "140.000", "note": "Pourboire"},
        format="json",
    )
    assert resent.status_code == 201
    summary = resent.json()["summary"]
    # Same figures as the first send: the second day's sale and stock stay on the second day.
    assert (summary["sales_total"], summary["products"][0]["remaining"]) == ("140.000", "7.000")
    assert resent.json()["closing"]["status"] == "submitted"
    # Still on the second day, which runs.
    assert sell(day, "1", "28.000").status_code == 201


def test_a_driver_only_sees_their_own_days(day):
    other = client_for(MembershipFactory.create(role=Role.DRIVER))
    first = day["api"].get(reverse("my-day-list")).json()[0]

    assert other.get(reverse("my-day-list")).json() == []
    assert other.get(reverse("my-day-detail", args=[first["id"]])).status_code == 404
    assert (
        other.post(reverse("my-past-day-closing", args=[first["id"]]), {"counted_cash": "1"}, format="json").status_code
        == 404
    )


def test_the_office_history_filters_by_driver_and_dates(day):
    day["api"].post(reverse("my-day-closing"), {"counted_cash": "50.000"}, format="json")
    today = timezone.localdate()

    def rows(**params):
        return day["office"].get(reverse("day-closing-list"), params).json()

    assert len(rows(search="Camion 1")) == 1
    assert rows(search="personne") == []
    assert len(rows(date_from=today.isoformat(), date_to=today.isoformat())) == 1
    assert rows(date_from=(today + dt.timedelta(days=1)).isoformat()) == []
