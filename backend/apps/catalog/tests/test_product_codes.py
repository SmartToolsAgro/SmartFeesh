import pytest
from django.core.management import call_command

from apps.catalog import services
from apps.catalog.models import Product
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


def test_the_command_reports_then_applies_the_owner_list(capsys):
    organization = OrganizationFactory.create()
    ProductFactory.create(organization=organization, name="Saumon entier", reference="SAU")

    call_command("set_product_codes", "--organization", str(organization.pk))
    assert references(organization)["Saumon entier"] == "SAU"
    call_command("set_product_codes", "--organization", str(organization.pk), "--apply")

    assert references(organization)["Saumon entier"] == "ART0034"
    assert len(PRODUCT_CODES) == 39
    assert "1 code(s) written" in capsys.readouterr().out
