"""The public site: a visitor reads the catalogue and sends a quote request or an order; the office handles it
(D-186)."""

import functools
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog import selectors as catalog
from apps.catalog.tests.factories import ProductFactory, ProductPriceFactory
from apps.core.models import AuditLog, Role
from apps.core.tests.factories import MembershipFactory, OrganizationFactory
from apps.notifications.models import Notification
from apps.storefront import services
from apps.storefront.models import WebRequest, WebRequestStatus

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _reset_throttles():
    cache.clear()


@pytest.fixture
def shop(settings):
    """Every active product is on the site: dorade first at 29.500 DT with a text, crevette and poulpe as they are
    ("prix sur demande"), loup hidden by the office; the archived product never shows."""
    organization = OrganizationFactory.create(name="Frutti Del Mare")
    settings.PUBLIC_SITE_ORGANIZATION_ID = organization.pk
    owner = MembershipFactory.create(organization=organization, role=Role.OWNER)
    dorade = ProductFactory.create(organization=organization, name="Dorade royale", illustration="fish")
    ProductPriceFactory.create(product=dorade, price=Decimal("28.000"))
    shrimp = ProductFactory.create(organization=organization, name="Crevette royale", illustration="shrimp")
    bass = ProductFactory.create(organization=organization, name="Loup de mer", illustration="bass")
    octopus = ProductFactory.create(organization=organization, name="Poulpe", illustration="octopus")
    archived = ProductFactory.create(organization=organization, name="Ancien produit")
    change = functools.partial(services.update_site_product, organization=organization, actor=owner.user)
    dorade_site = {"web_price": Decimal("29.500"), "description": "Pêchée à Sfax", "position": 0}
    change(product_id=dorade.pk, changes=dorade_site)
    change(product_id=bass.pk, changes={"web_price": Decimal("31.000"), "is_published": False})
    change(product_id=archived.pk, changes={"web_price": Decimal("10.000")})
    archived.is_active = False
    archived.save()
    return {
        "organization": organization,
        "owner": owner,
        "dorade": dorade,
        "shrimp": shrimp,
        "bass": bass,
        "octopus": octopus,
        "archived": archived,
    }


def order(shop, **changes):
    payload = {
        "kind": "order",
        "full_name": "Restaurant La Marsa",
        "phone": "98 123 456",
        "city": "Sfax",
        "lines": [{"product": shop["dorade"].pk, "quantity": "12.5"}, {"product": shop["shrimp"].pk, "quantity": "3"}],
    }
    payload.update(changes)
    return payload


@pytest.mark.parametrize(
    ("typed", "stored"),
    [
        ("98123456", "+216 98 123 456"),
        ("98 123 456", "+216 98 123 456"),
        ("+216 98.123.456", "+216 98 123 456"),
        ("0021674123456", "+216 74 123 456"),
        ("+33 6 12 34 56 78", "+33612345678"),
    ],
)
def test_phone_numbers_are_written_one_way(typed, stored):
    assert services.normalize_phone(typed) == stored


@pytest.mark.parametrize("typed", ["", "1234", "12345678", "98 123 45", "+216 98 123 4567", "téléphone", "+1234"])
def test_a_wrong_phone_number_is_refused(typed):
    with pytest.raises(ValidationError):
        services.normalize_phone(typed)


def test_the_catalogue_shows_the_site_products_with_their_web_price_only(shop):
    answer = APIClient().get(reverse("site-catalog"))
    assert answer.status_code == 200
    body = answer.json()
    assert body["company"] == "Frutti Del Mare"
    # Every active product, the ones the office placed first, then by name; the hidden and archived ones are not.
    shown = [(product["name"], product["web_price"], product["description"]) for product in body["products"]]
    assert shown == [
        ("Dorade royale", "29.500", "Pêchée à Sfax"),
        ("Crevette royale", None, ""),
        ("Poulpe", None, ""),
    ]
    # The web price only: never the day's price (28.000), a cost or the stock.
    assert {key for product in body["products"] for key in product if "price" in key} == {"web_price"}
    assert {category["id"] for category in body["categories"]} == {
        shop["dorade"].category_id,
        shop["shrimp"].category_id,
        shop["octopus"].category_id,
    }


def test_an_order_is_saved_and_tells_the_office(shop):
    answer = APIClient().post(reverse("site-requests"), order(shop), format="json")
    assert answer.status_code == 201, answer.json()
    request = WebRequest.objects.get()
    assert answer.json() == {"number": request.number, "kind": "order"}
    assert request.phone == "+216 98 123 456"
    assert request.status == WebRequestStatus.NEW
    # Each line keeps the web price the visitor saw.
    assert [(line.product, str(line.quantity), line.web_price) for line in request.lines.all()] == [
        (shop["dorade"], "12.500", Decimal("29.500")),
        (shop["shrimp"], "3.000", None),
    ]
    assert AuditLog.objects.filter(action="web_request.received", target_id=str(request.pk)).exists()
    notification = Notification.objects.get(kind="web_order")
    assert notification.params == {"number": request.number, "name": "Restaurant La Marsa", "phone": request.phone}
    assert notification.link == f"/demandes-site/{request.pk}"


def test_the_phone_number_is_required(shop):
    client = APIClient()
    missing = order(shop)
    del missing["phone"]
    assert client.post(reverse("site-requests"), missing, format="json").status_code == 400
    wrong = client.post(reverse("site-requests"), order(shop, phone="12"), format="json")
    assert wrong.status_code == 400
    assert "phone" in wrong.json()
    assert not WebRequest.objects.exists()


def test_an_order_needs_a_product_a_quote_a_product_or_a_message(shop):
    client = APIClient()
    assert client.post(reverse("site-requests"), order(shop, lines=[]), format="json").status_code == 400
    empty_quote = order(shop, kind="quote", lines=[])
    assert client.post(reverse("site-requests"), empty_quote, format="json").status_code == 400
    quote = order(shop, kind="quote", lines=[], message="Prix du loup pour 20 kg par semaine ?")
    assert client.post(reverse("site-requests"), quote, format="json").status_code == 201


@pytest.mark.parametrize(
    "lines",
    [
        [{"product": 999999, "quantity": "1"}],
        [{"product": "archived", "quantity": "1"}],
        [{"product": "bass", "quantity": "1"}],
        [{"product": "dorade", "quantity": "0"}],
        [{"product": "dorade", "quantity": "1"}, {"product": "dorade", "quantity": "2"}],
    ],
)
def test_products_not_shown_on_the_site_empty_or_repeated_lines_are_refused(shop, lines):
    for line in lines:
        if isinstance(line["product"], str):
            line["product"] = shop[line["product"]].pk
    answer = APIClient().post(reverse("site-requests"), order(shop, lines=lines), format="json")
    assert answer.status_code == 400
    assert "lines" in answer.json()


def test_another_companys_product_cannot_be_ordered(shop):
    other = ProductFactory.create(organization=OrganizationFactory.create())
    lines = [{"product": other.pk, "quantity": "1"}]
    assert APIClient().post(reverse("site-requests"), order(shop, lines=lines), format="json").status_code == 400


def test_robots_filling_the_hidden_field_are_refused(shop):
    answer = APIClient().post(reverse("site-requests"), order(shop, website="http://spam"), format="json")
    assert answer.status_code == 400
    assert not WebRequest.objects.exists()


def test_one_address_cannot_flood_the_office(shop):
    client = APIClient()
    answers = [client.post(reverse("site-requests"), order(shop), format="json").status_code for _ in range(11)]
    assert answers[:10] == [201] * 10
    assert answers[10] == 429


def test_the_office_lists_and_closes_requests(shop):
    APIClient().post(reverse("site-requests"), order(shop), format="json")
    request = WebRequest.objects.get()
    office = APIClient()
    office.force_authenticate(shop["owner"].user)

    listed = office.get(reverse("web-request-list"), {"status": "new"}).json()
    assert [row["number"] for row in listed["results"]] == [request.number]
    assert office.get(reverse("web-request-list"), {"search": "98 123"}).json()["count"] == 1
    assert office.get(reverse("web-request-list"), {"search": request.number}).json()["count"] == 1

    done = office.post(
        reverse("web-request-status", args=[request.pk]),
        {"status": "handled", "office_note": "Livré demain matin, 28 DT/kg"},
        format="json",
    )
    assert done.status_code == 200
    assert done.json()["status"] == "handled"
    assert done.json()["handled_by"] is not None
    assert AuditLog.objects.filter(action="web_request.status_changed").count() == 1


def test_an_accountant_reads_but_does_not_close_and_a_driver_sees_nothing(shop):
    APIClient().post(reverse("site-requests"), order(shop), format="json")
    request = WebRequest.objects.get()
    accountant = APIClient()
    accountant.force_authenticate(
        MembershipFactory.create(organization=shop["organization"], role=Role.ACCOUNTANT).user
    )
    assert accountant.get(reverse("web-request-detail", args=[request.pk])).status_code == 200
    status_url = reverse("web-request-status", args=[request.pk])
    assert accountant.post(status_url, {"status": "handled"}, format="json").status_code == 403
    driver = APIClient()
    driver.force_authenticate(MembershipFactory.create(organization=shop["organization"], role=Role.DRIVER).user)
    assert driver.get(reverse("web-request-list")).status_code == 403


def test_another_company_never_sees_the_requests(shop):
    APIClient().post(reverse("site-requests"), order(shop), format="json")
    request = WebRequest.objects.get()
    stranger = APIClient()
    stranger.force_authenticate(MembershipFactory.create(role=Role.OWNER).user)
    assert stranger.get(reverse("web-request-detail", args=[request.pk])).status_code == 404
    assert stranger.get(reverse("web-request-list")).json()["count"] == 0


# ---- The office chooses what the site shows (D-186) ----


def office_client(membership):
    client = APIClient()
    client.force_authenticate(membership.user)
    return client


def test_the_office_sees_every_product_and_sets_what_the_site_shows(shop):
    office = office_client(shop["owner"])
    listed = office.get(reverse("site-product-list")).json()
    # Every active product of the application, the placed ones first, then by name; the archived one is left out.
    names = [row["product_name"] for row in listed]
    assert names == ["Dorade royale", "Crevette royale", "Loup de mer", "Poulpe"]
    dorade, shrimp, bass, _octopus = listed
    assert (dorade["day_price"], dorade["web_price"], dorade["is_published"]) == ("28.000", "29.500", True)
    assert (shrimp["web_price"], shrimp["is_published"], shrimp["description"]) == (None, True, "")
    assert bass["is_published"] is False

    url = reverse("site-product-detail", args=[shop["shrimp"].pk])
    changed = office.patch(url, {"web_price": "42.000", "position": 1}, format="json")
    assert changed.status_code == 200, changed.json()
    assert changed.json()["web_price"] == "42.000"
    assert changed.json()["description"] == ""  # what is not sent does not change
    assert office.patch(url, {"web_price": "0"}, format="json").status_code == 400
    assert office.patch(url, {"web_price": None}, format="json").json()["web_price"] is None

    def on_site():
        return [product["name"] for product in APIClient().get(reverse("site-catalog")).json()["products"]]

    assert office.patch(url, {"is_published": False}, format="json").json()["is_published"] is False
    assert on_site() == ["Dorade royale", "Poulpe"]
    office.patch(url, {"is_published": True}, format="json")
    assert on_site() == ["Dorade royale", "Crevette royale", "Poulpe"]
    actions = set(AuditLog.objects.filter(action__startswith="site_product.").values_list("action", flat=True))
    assert actions == {"site_product.changed"}
    assert office.patch(reverse("site-product-detail", args=[999999]), {}, format="json").status_code == 404


def test_a_new_product_of_the_application_shows_on_the_site_at_once(shop):
    ProductFactory.create(organization=shop["organization"], name="Seiche", illustration="squid")
    names = [product["name"] for product in APIClient().get(reverse("site-catalog")).json()["products"]]
    assert "Seiche" in names


def test_the_web_price_never_changes_the_days_price(shop):
    office = office_client(shop["owner"])
    office.patch(reverse("site-product-detail", args=[shop["dorade"].pk]), {"web_price": "35"}, format="json")
    # Read again through the catalogue, which gives the price in force now.
    dorade = catalog.product_of(shop["organization"], shop["dorade"].pk)
    assert catalog.current_price_of(dorade) == Decimal("28.000")


def test_an_archived_product_cannot_be_put_on_the_site(shop):
    office = office_client(shop["owner"])
    url = reverse("site-product-detail", args=[shop["archived"].pk])
    answer = office.patch(url, {"is_published": True}, format="json")
    assert answer.status_code == 400
    assert "product" in answer.json()


def test_only_owners_and_managers_change_the_site(shop):
    organization = shop["organization"]
    url = reverse("site-product-detail", args=[shop["dorade"].pk])
    manager = office_client(MembershipFactory.create(organization=organization, role=Role.MANAGER))
    assert manager.patch(url, {"web_price": "30"}, format="json").status_code == 200
    accountant = office_client(MembershipFactory.create(organization=organization, role=Role.ACCOUNTANT))
    assert accountant.get(reverse("site-product-list")).status_code == 200
    assert accountant.patch(url, {"web_price": "31"}, format="json").status_code == 403
    driver = office_client(MembershipFactory.create(organization=organization, role=Role.DRIVER))
    assert driver.get(reverse("site-product-list")).status_code == 403
    stranger = office_client(MembershipFactory.create(role=Role.OWNER))
    assert stranger.patch(url, {"web_price": "1"}, format="json").status_code == 404


# ---- The site's contact details, set in the office app (D-186) ----


def test_the_office_sets_the_phone_the_site_shows(shop):
    office = office_client(shop["owner"])
    empty = office.get(reverse("site-settings")).json()
    assert empty == {"phone": "", "whatsapp": "", "email": "", "address": "", "opening_hours": ""}
    assert APIClient().get(reverse("site-catalog")).json()["contact"]["phone"] == ""

    saved = office.put(
        reverse("site-settings"),
        {
            "phone": "74 123 456",
            "whatsapp": "98123456",
            "email": "contact@fruttidelmare.com",
            "address": "Sakiet Ezzit",
        },
        format="json",
    )
    assert saved.status_code == 200, saved.json()
    assert saved.json()["phone"] == "+216 74 123 456"
    assert saved.json()["whatsapp"] == "+216 98 123 456"
    contact = APIClient().get(reverse("site-catalog")).json()["contact"]
    assert contact == {
        "phone": "+216 74 123 456",
        "whatsapp": "+216 98 123 456",
        "email": "contact@fruttidelmare.com",
        "address": "Sakiet Ezzit",
        "opening_hours": "",
    }
    assert AuditLog.objects.filter(action="site_settings.changed").count() == 1

    # A wrong number is refused and nothing changes; an empty one hides the line.
    wrong = office.put(reverse("site-settings"), {"phone": "123"}, format="json")
    assert wrong.status_code == 400
    assert "phone" in wrong.json()
    assert office.get(reverse("site-settings")).json()["phone"] == "+216 74 123 456"
    cleared = office.put(reverse("site-settings"), {"phone": ""}, format="json").json()
    assert cleared["phone"] == ""
    assert cleared["email"] == ""


def test_only_owners_and_managers_change_the_site_contact(shop):
    organization = shop["organization"]
    manager = office_client(MembershipFactory.create(organization=organization, role=Role.MANAGER))
    assert manager.put(reverse("site-settings"), {"phone": "74123456"}, format="json").status_code == 200
    accountant = office_client(MembershipFactory.create(organization=organization, role=Role.ACCOUNTANT))
    assert accountant.get(reverse("site-settings")).json()["phone"] == "+216 74 123 456"
    assert accountant.put(reverse("site-settings"), {"phone": "74123457"}, format="json").status_code == 403
    driver = office_client(MembershipFactory.create(organization=organization, role=Role.DRIVER))
    assert driver.get(reverse("site-settings")).status_code == 403
    stranger = office_client(MembershipFactory.create(role=Role.OWNER))
    assert stranger.get(reverse("site-settings")).json()["phone"] == ""
