import pytest

from tooling.import_contracts import boundary_violation


@pytest.mark.parametrize(
    ("importer", "imported"),
    [
        ("apps.sales.services", "apps.sales.models"),
        ("apps.sales.services", "apps.inventory.services"),
        ("apps.sales.api.views", "apps.inventory.selectors"),
        ("apps.sales.models", "apps.core.models"),
        ("apps.sales.tests.test_sales", "apps.inventory.tests.factories"),
        ("apps.sales.services", "django.db"),
        ("apps.demo.management.commands.prepare_client_start", "apps.inventory.models"),
    ],
)
def test_allowed_imports(importer, imported):
    assert boundary_violation(importer, imported) is None


@pytest.mark.parametrize(
    ("importer", "imported"),
    [
        ("apps.sales.services", "apps.inventory.models"),
        ("apps.sales.api.views", "apps.inventory.api.serializers"),
        ("apps.sales.services", "apps.inventory"),
        ("apps.core.services", "apps.sales.services"),
        ("apps.demo.management.commands.seed_dev", "apps.inventory.models"),
    ],
)
def test_forbidden_imports(importer, imported):
    assert boundary_violation(importer, imported) is not None
