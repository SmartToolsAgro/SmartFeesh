import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.catalog import selectors, services
from apps.catalog.models import KILOGRAM, Category, Product
from apps.catalog.product_codes import PRODUCT_CODES
from apps.catalog.tests.factories import ProductFactory
from apps.core.models import AuditLog
from apps.core.tests.factories import OrganizationFactory

pytestmark = pytest.mark.django_db


def references(organization):
    return dict(Product.objects.for_organization(organization).values_list("name", "reference"))


def test_codes_go_into_the_reference_of_the_product_with_the_same_name():
    organization = OrganizationFactory.create()
    ProductFactory.create(organization=organization, name="Crevette Décortiquée", reference="P-1")
    ProductFactory.create(organization=organization, name="CREVETTE  DECORTIQUE", reference="P-2")
    ProductFactory.create(organization=organization, name="Seiches noir", reference="P-3", min_stock=5)
    ProductFactory.create(organization=organization, name="Poulpe gros", reference="ART0016")
    ProductFactory.create(organization=organization, name="Calamar", reference="X")
    ProductFactory.create(organization=organization, name="Autre", reference="ART0012")
    ProductFactory.create(organization=organization, name="Crevette tigrée", reference="P-4")
    codes = [
        ("ART0009", "Crevette décortiqué"),
        ("ART0011", "seiches Noir "),
        ("ART0016", "poulpe gros"),
        ("ART0020", "crevette royale"),
        ("ART0012", "Calamar"),
        ("ART0047", "MAKLOUBA ROSE CONGELE M0"),
        ("ART0055", "Maklouba rosé congelé M0"),
    ]

    preview = services.set_product_codes(organization=organization, actor=None, codes=codes, apply=False)

    assert [outcome.status for outcome in preview] == [
        "set",  # only "CREVETTE  DECORTIQUE" has the same name once accents, case and spaces are ignored
        "set",
        "unchanged",
        "not_found",
        "code_taken",
        "same_name_in_list",
        "same_name_in_list",
    ]
    assert references(organization)["Seiches noir"] == "P-3"  # a preview writes nothing

    services.set_product_codes(organization=organization, actor=None, codes=codes, apply=True)

    after = references(organization)
    assert after["CREVETTE  DECORTIQUE"] == "ART0009"
    assert after["Crevette Décortiquée"] == "P-1"
    assert after["Seiches noir"] == "ART0011"
    assert after["Calamar"] == "X"
    assert Product.objects.get(name="Seiches noir").min_stock == 5  # nothing but the reference changes
    assert AuditLog.objects.filter(action="product.updated").count() == 2


def test_the_owner_list_gives_maklouba_m0_its_chosen_code():
    organization = OrganizationFactory.create()
    ProductFactory.create(organization=organization, name="Maklouba rosé congelé M0", reference="MAK-M0")

    outcomes = services.set_product_codes(organization=organization, actor=None, codes=PRODUCT_CODES, apply=True)

    assert references(organization)["Maklouba rosé congelé M0"] == "ART0047"
    assert not any(outcome.status == "same_name_in_list" for outcome in outcomes)


def test_the_command_reports_then_applies_the_owner_list(capsys):
    organization = OrganizationFactory.create()
    ProductFactory.create(organization=organization, name="Saumon entier", reference="SAU")

    call_command("set_product_codes", "--organization", str(organization.pk))
    assert references(organization)["Saumon entier"] == "SAU"
    call_command("set_product_codes", "--organization", str(organization.pk), "--apply")

    assert references(organization)["Saumon entier"] == "ART0034"
    assert len(PRODUCT_CODES) == 38
    # The owner chose ART0047 for "Maklouba rosé congelé M0"; ART0055 is assigned to nothing.
    assert ("ART0047", "MAKLOUBA ROSE CONGELE M0") in PRODUCT_CODES
    assert all(code != "ART0055" for code, _name in PRODUCT_CODES)
    assert "1 code(s) written" in capsys.readouterr().out


def test_missing_articles_are_created_without_a_price_when_asked():
    organization = OrganizationFactory.create()
    ProductFactory.create(organization=organization, name="Calamar", reference="CA-005")
    ProductFactory.create(organization=organization, name="Autre", reference="ART0016")
    codes = [("ART0032", "Calamar"), ("ART0016", "poulpe gros"), ("ART0050", " FILET PANGA ")]
    products = Product.objects.for_organization(organization)
    unsorted = Category.objects.for_organization(organization).filter(name="À classer")

    preview = services.set_product_codes(
        organization=organization, actor=None, codes=codes, apply=False, create_missing=True
    )

    # "poulpe gros" matches no product, but another product already has its code: it is not created.
    assert [outcome.status for outcome in preview] == ["set", "code_taken", "new"]
    assert products.count() == 2  # a preview creates nothing
    assert not unsorted.exists()

    services.set_product_codes(organization=organization, actor=None, codes=codes, apply=True, create_missing=True)

    created = products.get(reference="ART0050")
    assert (created.name, created.category.name, created.base_unit.code) == ("FILET PANGA", "À classer", KILOGRAM)
    assert not created.prices.exists()
    assert selectors.price_in_force(created, timezone.now()) is None
    assert references(organization)["Calamar"] == "ART0032"
    assert products.count() == 3
    assert AuditLog.objects.filter(action="product.created").count() == 1
    assert AuditLog.objects.filter(action="category.created").count() == 1

    again = services.set_product_codes(
        organization=organization, actor=None, codes=codes, apply=True, create_missing=True
    )

    # Run twice, it creates nothing more: the new product now matches by name and has its code.
    assert [outcome.status for outcome in again] == ["unchanged", "code_taken", "unchanged"]
    assert products.count() == 3
    assert unsorted.count() == 1


def test_the_command_creates_the_missing_articles_only_when_told(capsys):
    organization = OrganizationFactory.create()
    products = Product.objects.for_organization(organization)

    call_command("set_product_codes", "--organization", str(organization.pk), "--apply")
    assert not products.exists()
    call_command("set_product_codes", "--organization", str(organization.pk), "--create-missing")
    assert not products.exists()
    assert "38 product(s) to create" in capsys.readouterr().out

    call_command("set_product_codes", "--organization", str(organization.pk), "--create-missing", "--apply")

    assert products.count() == 38
    assert set(products.values_list("category__name", flat=True)) == {"À classer"}
    assert "38 product(s) created" in capsys.readouterr().out
