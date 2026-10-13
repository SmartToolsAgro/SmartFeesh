"""A driver's days are windows of a date (D-134): each one balances its own stock, a sale counts on the day that
covers the moment it was made (D-133), and a sent closing keeps its figures while the office sees what changed."""

import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.tests.factories import ProductFactory, ProductPriceFactory
from apps.core.models import Role
from apps.core.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.dayclose import selectors
from apps.fleet import services as fleet
from apps.fleet.models import DriverDay
from apps.inventory import services as inventory
from apps.inventory.models import LossReason, MovementKind
from apps.inventory.tests.factories import BatchFactory, StockLocationFactory
from apps.partners import services as partners
from apps.sales.models import Sale

pytestmark = pytest.mark.django_db

# The date everything happens on; the clock of each test is set by hand (`clock`).
DAY = timezone.localdate() - dt.timedelta(days=2)
DAY_BEFORE = DAY - dt.timedelta(days=1)
NEXT_DAY = DAY + dt.timedelta(days=1)


def at(hour, minute=0, *, day=DAY):
    return timezone.make_aware(dt.datetime.combine(day, dt.time(hour, minute)))


@pytest.fixture
def clock(monkeypatch):
    """Set the server's clock: `clock(at(10))`."""

    def set_to(moment):
        monkeypatch.setattr(timezone, "now", lambda: moment)

    return set_to


def client_for(membership):
    client = APIClient()
    client.force_authenticate(membership.user)
    return client


def load(road, kg, *, on=None, back=False):
    """Load `kg` of dorade into the truck (or bring them back to the cold room), today or on an earlier day."""
    places = (road["truck"].location, road["room"]) if back else (road["room"], road["truck"].location)
    inventory.create_transfer(
        organization=road["organization"],
        actor=None,
        from_location=places[0],
        to_location=places[1],
        transferred_on=on or timezone.localdate(),
        lines=[{"product": road["product"], "quantity": Decimal(kg)}],
        validate=True,
    )


@pytest.fixture
def road(clock):
    """A driver whose truck kept 3 kg of dorade from the day before and got 12 kg more at 08:00. Dorade is 28 DT.
    The driver started the day at 08:30 with 50 DT. The clock is left at 08:30."""
    clock(at(7))
    organization = OrganizationFactory.create()
    actor = UserFactory.create()
    driver = MembershipFactory.create(organization=organization, role=Role.DRIVER)
    office = MembershipFactory.create(organization=organization, role=Role.MANAGER)
    room = StockLocationFactory.create(organization=organization, name="Chambre froide 1")
    truck = fleet.create_truck(
        organization=organization, actor=actor, name="Camion 1", plate="101 TU 2001", driver=driver.user
    )
    product = ProductFactory.create(organization=organization, name="Dorade royale", reference="DO-003")
    ProductPriceFactory.create(product=product, price=Decimal("28.000"), valid_from=at(0, day=DAY - dt.timedelta(5)))
    batch = BatchFactory.create(organization=organization, product=product, received_on=DAY_BEFORE)
    inventory.post_movement(
        organization=organization,
        actor=None,
        kind=MovementKind.RECEIPT,
        batch=batch,
        quantity="40",
        to_location=room,
        occurred_at=at(7, day=DAY_BEFORE),
    )
    customer = partners.create_customer(
        organization=organization, actor=actor, name="Restaurant Le Port", credit_limit=Decimal("5000.000")
    )
    road = {
        "api": client_for(driver),
        "office": client_for(office),
        "organization": organization,
        "driver": driver,
        "product": product,
        "room": room,
        "truck": truck,
        "customer": customer,
    }
    load(road, "3", on=DAY_BEFORE)
    clock(at(8))
    load(road, "12")
    clock(at(8, 30))
    assert road["api"].post(reverse("my-day"), {"opening_cash": "50"}, format="json").status_code == 201
    return road


def sell(road, kg, paid="0", *, made_at=None):
    body = {
        "customer": road["customer"].pk,
        "location": road["truck"].location_id,
        "confirm_now": True,
        "amount_paid": paid,
        "payment_method": "cash",
        "lines": [{"product": road["product"].pk, "quantity": kg}],
    }
    if made_at is not None:
        body["sold_at"] = made_at.isoformat()
    return road["api"].post(reverse("sale-list"), body, format="json")


def close(road, counted):
    return road["api"].post(reverse("my-day-closing"), {"counted_cash": counted}, format="json")


def driver_day(road, number):
    return DriverDay.objects.select_related("truck__location", "driver").get(
        organization=road["organization"], date=DAY, number=number
    )


def stock_line(road, number):
    """The dorade line of one of the driver's days, computed now from the records."""
    (line,) = selectors.day_summary(road["organization"], driver_day(road, number))["products"]
    return {name: str(value) for name, value in line.items() if name not in ("product_id", "product_name")}


def morning_then_second_day(road, clock):
    """Day 1: 5 kg sold at 10:00, closing sent at 12:00 with the right cash. Day 2 started at 12:10 with 20 DT."""
    clock(at(10))
    assert sell(road, "5", "100.000").status_code == 201  # 140 DT, 100 in cash
    clock(at(12))
    assert close(road, "150.000").status_code == 201
    clock(at(12, 10))
    assert road["api"].post(reverse("my-day"), {"opening_cash": "20"}, format="json").json()["number"] == 2


def test_a_first_day_and_a_second_day_of_the_same_date_both_balance(road, clock):
    """The second day starts from what the truck held when the first ended (10 kg), not from the start of the
    date (3 kg): opening + loaded - returned - sold - lost = left for both, with no gap to explain."""
    morning_then_second_day(road, clock)
    clock(at(13))
    load(road, "4")
    clock(at(14))
    assert sell(road, "2", "56.000").status_code == 201
    inventory.record_loss(
        organization=road["organization"],
        actor=road["driver"].user,
        location=road["truck"].location,
        product=road["product"],
        quantity="1",
        reason=LossReason.values[0],
        lost_on=DAY,
    )
    clock(at(16))
    load(road, "2", back=True)

    first = stock_line(road, 1)
    second = stock_line(road, 2)

    assert first == {
        "opening": "3.000",
        "loaded": "12.000",
        "sold": "5.000",
        "lost": "0.000",
        "returned": "0.000",
        "remaining": "10.000",
        "unexplained": "0.000",
    }
    assert second == {
        "opening": "10.000",
        "loaded": "4.000",
        "sold": "2.000",
        "lost": "1.000",
        "returned": "2.000",
        "remaining": "9.000",
        "unexplained": "0.000",
    }
    # The cash of each day is its own too.
    money = selectors.day_summary(road["organization"], driver_day(road, 2))
    assert (money["sales_count"], money["expected_cash"]) == (1, Decimal("76.000"))  # 20 at the start + 56
    # Sent, the second day keeps the same figures, and the first still balances the next morning.
    clock(at(18))
    sent = close(road, "76.000").json()["summary"]["products"][0]
    assert (sent["opening"], sent["remaining"], sent["unexplained"]) == ("10.000", "9.000", "0.000")
    clock(at(9, day=NEXT_DAY))
    assert stock_line(road, 1) == first
    assert stock_line(road, 2) == second


def test_stock_that_moved_without_a_record_shows_on_the_day_it_moved_only(road, clock):
    morning_then_second_day(road, clock)
    clock(at(13))
    inventory.post_movement(
        organization=road["organization"],
        actor=None,
        kind=MovementKind.ADJUSTMENT,
        batch=road["product"].batches.get(),
        quantity="2",
        from_location=road["truck"].location,
        reason="Test",
    )

    assert stock_line(road, 1)["unexplained"] == "0.000"
    second = stock_line(road, 2)
    assert (second["opening"], second["remaining"], second["unexplained"]) == ("10.000", "8.000", "-2.000")


def test_a_sale_made_before_the_closing_and_received_after_it_counts_on_that_day(road, clock):
    """Made at 11:00 without connection, received at 15:00, after the first day was sent at 12:00: it is the
    first day's sale. The closing keeps what the driver sent; the office sees what changed and still decides."""
    morning_then_second_day(road, clock)
    clock(at(14))
    assert sell(road, "2", "56.000").status_code == 201
    first_id = driver_day(road, 1).pk
    clock(at(15))

    late = sell(road, "1", "28.000", made_at=at(11))

    assert late.status_code == 201
    assert Sale.objects.get(pk=late.json()["id"]).sold_at == at(11)
    organization = road["organization"]
    live_first = selectors.day_summary(organization, driver_day(road, 1))
    assert (live_first["sales_count"], live_first["sales_total"], live_first["expected_cash"]) == (
        2,
        Decimal("168.000"),
        Decimal("178.000"),
    )
    first = stock_line(road, 1)
    assert (first["sold"], first["remaining"], first["unexplained"]) == ("6.000", "9.000", "0.000")
    # The second day takes none of it: its own sale, and an opening stock one kilo lower.
    live_second = selectors.day_summary(organization, driver_day(road, 2))
    assert (live_second["sales_count"], live_second["sales_total"]) == (1, Decimal("56.000"))
    second = stock_line(road, 2)
    assert (second["opening"], second["sold"], second["remaining"], second["unexplained"]) == (
        "9.000",
        "2.000",
        "7.000",
        "0.000",
    )

    # The driver's phone and the office still read the closing as it was sent.
    as_sent = road["api"].get(reverse("my-day-detail", args=[first_id])).json()
    assert (as_sent["summary"]["sales_total"], as_sent["closing"]["expected_cash"]) == ("140.000", "150.000")
    row = next(r for r in road["office"].get(reverse("day-closing-list")).json() if r["number"] == 1)
    detail = road["office"].get(reverse("day-closing-detail", args=[row["id"]])).json()
    assert (detail["expected_cash"], detail["summary"]["sales_count"]) == ("150.000", 1)
    assert detail["summary"]["products"][0]["sold"] == "5.000"
    # ... and the office sees, figure by figure, that the records have moved since.
    assert [(c["figure"], c["product_name"], c["sent"], c["live"]) for c in detail["changes_since_sent"]] == [
        ("sales_count", "", "1.000", "2.000"),
        ("sales_total", "", "140.000", "168.000"),
        ("cash_received", "", "100.000", "128.000"),
        ("expected_cash", "", "150.000", "178.000"),
        ("sold", "Dorade royale", "5.000", "6.000"),
        ("remaining", "Dorade royale", "10.000", "9.000"),
    ]
    # It does not block the office: the day is approved as sent, and is then locked.
    approved = road["office"].post(reverse("day-closing-approve", args=[row["id"]])).json()
    assert (approved["status"], approved["expected_cash"], approved["changes_since_sent"]) == (
        "approved",
        "150.000",
        [],
    )
    assert sell(road, "1", "28.000", made_at=at(11, 30)).status_code == 403  # nothing more on an approved day


def test_nothing_changed_since_the_closing_was_sent_shows_no_difference(road, clock):
    morning_then_second_day(road, clock)
    clock(at(14))
    assert sell(road, "2", "56.000").status_code == 201  # the second day's sale leaves the first untouched

    row = next(r for r in road["office"].get(reverse("day-closing-list")).json() if r["number"] == 1)

    assert road["office"].get(reverse("day-closing-detail", args=[row["id"]])).json()["changes_since_sent"] == []


def test_the_day_sent_again_after_a_justification_takes_the_late_sale(road, clock):
    """The office's way to bring a sent day up to date: it asks, the driver sends again, and the new figures
    are those of the same window with the late sale in them."""
    morning_then_second_day(road, clock)
    first_id = driver_day(road, 1).pk
    clock(at(15))
    assert sell(road, "1", "28.000", made_at=at(11)).status_code == 201
    row = next(r for r in road["office"].get(reverse("day-closing-list")).json() if r["number"] == 1)
    road["office"].post(
        reverse("day-closing-justification", args=[row["id"]]), {"reason": "Une vente en plus ?"}, format="json"
    )

    # Asked, the phone shows the day's records, which the new send will keep: the cash to count against is right.
    asked = road["api"].get(reverse("my-day-detail", args=[first_id])).json()
    assert (asked["closing"]["status"], asked["summary"]["expected_cash"]) == ("justification", "178.000")

    clock(at(16))
    resent = road["api"].post(
        reverse("my-past-day-closing", args=[first_id]), {"counted_cash": "178.000", "note": "Vente hors réseau"}
    )

    assert resent.status_code == 201
    summary = resent.json()["summary"]
    assert (summary["sales_count"], summary["expected_cash"]) == (2, "178.000")
    assert (summary["products"][0]["sold"], summary["products"][0]["remaining"]) == ("6.000", "9.000")
    detail = road["office"].get(reverse("day-closing-detail", args=[row["id"]])).json()
    assert (detail["status"], detail["difference"], detail["changes_since_sent"]) == ("submitted", "0.000", [])
    assert timezone.localtime(driver_day(road, 1).ended_at) == at(12)  # the day still ends at its first send


def test_a_sale_made_after_the_day_was_sent_is_refused_until_a_new_day_is_started(road, clock):
    clock(at(10))
    assert sell(road, "5", "100.000").status_code == 201
    clock(at(12))
    assert close(road, "150.000").status_code == 201

    clock(at(12, 5))
    now = sell(road, "1", "28.000")
    clock(at(13))
    kept_on_the_phone = sell(road, "1", "28.000", made_at=at(12, 30))  # made after the send, received later

    for refused in (now, kept_on_the_phone):
        assert refused.status_code == 403
        assert refused.json()["detail"] == "Votre journée est clôturée : commencez une nouvelle journée."
    assert Sale.objects.count() == 1
    # A sale made before the send is still the first day's (sent, not approved).
    assert sell(road, "1", "28.000", made_at=at(11)).status_code == 201

    clock(at(13, 10))
    assert road["api"].post(reverse("my-day"), {"opening_cash": "0"}, format="json").json()["number"] == 2
    assert sell(road, "1", "28.000").status_code == 201
    # Between the two days the truck was not on any other day: the second day covers from the first one's end.
    assert sell(road, "1", "28.000", made_at=at(12, 30)).status_code == 201
    second = stock_line(road, 2)
    assert (second["opening"], second["sold"], second["remaining"], second["unexplained"]) == (
        "9.000",
        "2.000",
        "7.000",
        "0.000",
    )


def test_a_sale_made_after_the_closing_of_an_earlier_date_is_refused_with_its_date(road, clock):
    """Yesterday's day was sent at 18:00 and no other was started: a sale the phone says was made at 19:00,
    received this morning, cannot go on a new day of yesterday any more. Refused, so the phone reports it."""
    clock(at(18))
    assert close(road, "50.000").status_code == 201
    clock(at(9, day=NEXT_DAY))

    after = sell(road, "1", "28.000", made_at=at(19))
    before = sell(road, "1", "28.000", made_at=at(17))

    assert after.status_code == 403
    assert after.json()["detail"] == (
        f"Votre journée du {DAY:%d/%m/%Y} était déjà clôturée quand cette vente a été faite : "
        "elle n'est pas enregistrée. Prévenez le bureau."
    )
    assert before.status_code == 201  # made before the send: yesterday's sale, the day is not approved
    assert timezone.localtime(Sale.objects.get().sold_at) == at(17)
    assert sell(road, "1", "28.000").status_code == 201  # today no day is started yet: sold as before (D-133)


def test_a_late_sale_of_an_approved_first_day_is_refused_while_the_second_day_sells(road, clock):
    morning_then_second_day(road, clock)
    row = road["office"].get(reverse("day-closing-list")).json()[0]
    assert road["office"].post(reverse("day-closing-approve", args=[row["id"]])).status_code == 200
    clock(at(15))

    late = sell(road, "1", "28.000", made_at=at(11))

    assert late.status_code == 403
    assert late.json()["detail"] == "Votre journée est approuvée par le bureau : elle est fermée."
    assert sell(road, "1", "28.000").status_code == 201  # the second day runs
    assert sell(road, "1", "28.000", made_at=at(12, 30)).status_code == 201  # made during the second day
