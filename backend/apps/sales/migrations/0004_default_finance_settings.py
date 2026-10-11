"""Every existing organization gets its first finance settings version (D-056): Q5's answers, which the owner
changes from the settings screen. New organizations get it from `signals.py`."""

from decimal import Decimal

from django.db import migrations


def give_first_settings(apps, schema_editor):
    Organization = apps.get_model("core", "Organization")
    FinanceSettings = apps.get_model("sales", "FinanceSettings")
    for organization in Organization.objects.all():
        if FinanceSettings.objects.filter(organization=organization).exists():
            continue
        FinanceSettings.objects.create(
            organization=organization,
            valid_from=organization.created_at.date(),
            vat_rate=Decimal("19.00"),
            fiscal_stamp=Decimal("1.000"),
            prices_include_vat=False,
            withholding_rate=Decimal("0.00"),
            legal_name=organization.name,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0003_invoices"),
        ("core", "0001_initial"),
    ]

    operations = [migrations.RunPython(give_first_settings, migrations.RunPython.noop)]
