"""D-095: a validated sale is a delivery note numbered BL-<year>-<nnnn>. Sales validated before this change
(demo and staging data) get their BL number in the order they were validated."""

from django.db import migrations
from django.utils import timezone


def number_validated_sales(apps, schema_editor):
    Sale = apps.get_model("sales", "Sale")
    DocumentCounter = apps.get_model("sales", "DocumentCounter")
    sales = Sale.objects.filter(confirmed_at__isnull=False).order_by("organization_id", "confirmed_at", "id")
    for sale in sales:
        year = timezone.localdate(sale.confirmed_at).year
        counter, _ = DocumentCounter.objects.get_or_create(organization_id=sale.organization_id, series=f"BL-{year}")
        counter.last_number += 1
        counter.save(update_fields=["last_number"])
        sale.number = f"BL-{year}-{counter.last_number:04d}"
        sale.save(update_fields=["number"])


class Migration(migrations.Migration):
    dependencies = [("sales", "0006_customer_returns")]

    operations = [migrations.RunPython(number_validated_sales, migrations.RunPython.noop)]
