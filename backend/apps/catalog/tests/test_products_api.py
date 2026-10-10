import datetime as dt

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import Product
from apps.core.models import Role
from apps.core.tests.factories import MembershipFactory

from .factories import CategoryFactory, ProductFactory, ProductPriceFactory
from .test_products import image_upload

pytestmark = pytest.mark.django_db


@pytest.fixture
def manager():
    return MembershipFactory.create(role=Role.MANAGER)


@pytest.fixture
def api(manager):
    client = APIClient()
    client.force_authenticate(manager.user)
    return client


@pytest.fixture
def category(manager):
    return CategoryFactory.create(organization=manager.organization, name="Crustacés")


def client_for(membership):
    client = APIClient()
    client.force_authenticate(membership.user)
    return client


def product_payload(category, **fields):
    payload = {"reference": "CR-001", "name": "Crevette Royale", "category": category.pk, "sale_price": "42.000"}
    payload.update(fields)
    return payload


def create(api, category, **fields):
    return api.post(reverse("product-list"), product_payload(category, **fields), format="json")


def test_creating_a_product_answers_it_with_its_price_as_a_string(api, category):
    response = create(api, category, name_ar="قمرون ملكي", min_stock="20", storage_temp_max="4")

    assert response.status_code == 201
    body = response.json()
    assert body["reference"] == "CR-001"
    assert body["category"] == {"id": category.pk, "name": "Crustacés"}
    assert body["base_unit"] == "kg"
    assert body["min_stock"] == "20.000"
    assert body["storage_temp_min"] is None
    assert body["storage_temp_max"] == "4.0"
    assert body["current_price"] == "42.000"
    assert body["photo_url"] is None
    assert body["is_active"] is True


def test_a_business_rule_error_is_a_400_on_its_field(api, category):
    create(api, category)

    response = create(api, category, reference="cr-001")

    assert response.status_code == 400
    assert list(response.json()) == ["reference"]


def test_quantities_finer_than_a_gram_are_refused(api, category):
    response = create(api, category, min_stock="1.0005")

    assert response.status_code == 400
    assert "min_stock" in response.json()


def test_a_category_of_another_organization_is_unknown(api):
    theirs = CategoryFactory.create()

    response = create(api, theirs)

    assert response.status_code == 400
    assert "category" in response.json()


def test_drivers_and_accountants_read_the_catalogue_but_cannot_change_it(category):
    ProductFactory.create(organization=category.organization, category=category)
    for role in (Role.DRIVER, Role.ACCOUNTANT):
        client = client_for(MembershipFactory.create(role=role, organization=category.organization))

        assert client.get(reverse("product-list")).status_code == 200
        assert create(client, category, reference=f"X-{role}").status_code == 403
        assert client.post(reverse("category-list"), {"name": "X"}, format="json").status_code == 403


def test_anonymous_visitors_get_401():
    response = APIClient().get(reverse("product-list"))

    assert response.status_code == 401


def test_another_organization_products_are_invisible(api):
    theirs = ProductFactory.create()

    assert api.get(reverse("product-list")).json() == []
    assert api.get(reverse("product-detail", args=[theirs.pk])).status_code == 404
    assert api.patch(reverse("product-detail", args=[theirs.pk]), {"name": "X"}, format="json").status_code == 404
    assert api.post(reverse("product-archive", args=[theirs.pk])).status_code == 404
    assert api.get(reverse("product-prices", args=[theirs.pk])).status_code == 404


def test_the_list_filters_by_search_category_and_status(api, category, manager):
    fish = CategoryFactory.create(organization=manager.organization, name="Poissons")
    shrimp = create(api, category).json()
    dorade = create(api, fish, reference="DO-003", name="Dorade royale", sale_price="24.5").json()
    api.post(reverse("product-archive", args=[dorade["id"]]))
    url = reverse("product-list")

    def ids(**params):
        return [product["id"] for product in api.get(url, params).json()]

    assert ids() == [shrimp["id"]]
    assert ids(status="all") == [shrimp["id"], dorade["id"]]
    assert ids(status="archived") == [dorade["id"]]
    assert ids(status="all", category=fish.pk) == [dorade["id"]]
    assert ids(status="all", search="royale") == [shrimp["id"], dorade["id"]]
    assert api.get(url, {"status": "deleted"}).status_code == 400


def test_a_partial_update_keeps_the_other_fields(api, category):
    product = create(api, category, min_stock="20", illustration="shrimp").json()

    response = api.patch(reverse("product-detail", args=[product["id"]]), {"name": "Crevette"}, format="json")

    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["min_stock"], body["illustration"]) == ("Crevette", "20.000", "shrimp")
    assert body["current_price"] == "42.000"


def test_the_price_is_never_changed_by_an_update(api, category):
    product = create(api, category).json()

    api.patch(reverse("product-detail", args=[product["id"]]), {"sale_price": "1"}, format="json")

    assert api.get(reverse("product-detail", args=[product["id"]])).json()["current_price"] == "42.000"


def test_setting_a_price_keeps_the_history(api, category):
    product = create(api, category).json()
    url = reverse("product-prices", args=[product["id"]])
    tomorrow = timezone.now() + dt.timedelta(days=1)

    now_answer = api.post(url, {"price": "39.500"}, format="json")
    planned = api.post(url, {"price": "45", "valid_from": tomorrow.isoformat()}, format="json")

    assert now_answer.status_code == 201
    assert now_answer.json()["current_price"] == "39.500"
    assert planned.json()["current_price"] == "39.500"  # tomorrow's price is not in force yet
    history = api.get(url).json()
    assert [entry["price"] for entry in history] == ["45.000", "39.500", "42.000"]
    assert history[0]["created_by"] is not None


def test_a_price_in_the_past_is_refused(api, category):
    product = create(api, category).json()
    yesterday = timezone.now() - dt.timedelta(days=1)

    response = api.post(
        reverse("product-prices", args=[product["id"]]),
        {"price": "1", "valid_from": yesterday.isoformat()},
        format="json",
    )

    assert response.status_code == 400
    assert "valid_from" in response.json()


def test_archiving_and_restoring(api, category):
    product = create(api, category).json()

    archived = api.post(reverse("product-archive", args=[product["id"]]))
    restored = api.post(reverse("product-restore", args=[product["id"]]))

    assert archived.json()["is_active"] is False
    assert restored.json()["is_active"] is True


def test_categories_are_listed_created_and_renamed(api, category):
    created = api.post(reverse("category-list"), {"name": "Poissons"}, format="json")
    renamed = api.patch(reverse("category-detail", args=[category.pk]), {"name": "Crustacés frais"}, format="json")
    duplicate = api.post(reverse("category-list"), {"name": "poissons"}, format="json")

    assert created.status_code == 201
    assert renamed.json() == {"id": category.pk, "name": "Crustacés frais"}
    assert duplicate.status_code == 400
    assert [c["name"] for c in api.get(reverse("category-list")).json()] == ["Crustacés frais", "Poissons"]


def test_another_organization_category_cannot_be_renamed(api):
    theirs = CategoryFactory.create()

    response = api.patch(reverse("category-detail", args=[theirs.pk]), {"name": "X"}, format="json")

    assert response.status_code == 404


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def test_a_photo_is_uploaded_then_served_to_members_only(media, api, category, manager):
    product = create(api, category).json()
    url = reverse("product-photo", args=[product["id"]])

    uploaded = api.put(url, {"photo": image_upload()}, format="multipart")

    assert uploaded.status_code == 200
    photo_url = uploaded.json()["photo_url"]
    assert photo_url.startswith(f"{url}?v=")
    served = api.get(photo_url)
    assert served.status_code == 200
    assert served["Content-Type"] == "image/webp"
    assert "immutable" in served["Cache-Control"]
    assert b"".join(served.streaming_content).startswith(b"RIFF")

    driver = client_for(MembershipFactory.create(role=Role.DRIVER, organization=manager.organization))
    stranger = client_for(MembershipFactory.create(role=Role.MANAGER))
    assert driver.get(photo_url).status_code == 200
    assert stranger.get(photo_url).status_code == 404
    assert APIClient().get(photo_url).status_code == 401
    assert driver.put(url, {"photo": image_upload()}, format="multipart").status_code == 403


def test_a_photo_can_be_removed(media, api, category):
    product = create(api, category).json()
    url = reverse("product-photo", args=[product["id"]])
    api.put(url, {"photo": image_upload()}, format="multipart")

    removed = api.delete(url)

    assert removed.json()["photo_url"] is None
    assert api.get(url).status_code == 404


def test_a_file_that_is_not_an_image_is_a_400(media, api, category):
    product = create(api, category).json()
    upload = SimpleUploadedFile("x.jpg", b"nope", content_type="image/jpeg")
    response = api.put(reverse("product-photo", args=[product["id"]]), {"photo": upload}, format="multipart")

    assert response.status_code == 400
    assert "photo" in response.json()
    assert Product.objects.get(pk=product["id"]).photo.name == ""


def test_a_product_without_price_shows_none():
    product = ProductFactory.create()
    manager = MembershipFactory.create(role=Role.MANAGER, organization=product.organization)

    body = client_for(manager).get(reverse("product-detail", args=[product.pk])).json()

    assert body["current_price"] is None
    ProductPriceFactory.create(product=product)
    assert client_for(manager).get(reverse("product-detail", args=[product.pk])).json()["current_price"] == "42.000"
