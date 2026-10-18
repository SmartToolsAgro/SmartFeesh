"""The kept day figures said "paid with the sales cash" for all the cash beyond the purchase money, also the part the
driver paid out of pocket, so that part showed twice (D-182). Only that one figure is corrected; the cash expected,
counted and the gap do not change."""

from decimal import Decimal

from django.db import migrations


def split(apps, schema_editor):
    for name in ("DayClosing", "DayReopening"):
        model = apps.get_model("dayclose", name)
        for row in model.objects.filter(summary__has_key="owed_to_driver").iterator():
            summary = row.summary
            owed = Decimal(str(summary.get("owed_to_driver") or "0"))
            if owed <= 0:
                continue
            from_sales = Decimal(str(summary.get("purchases_from_sales") or "0"))
            summary["purchases_from_sales"] = str(max(from_sales - owed, Decimal("0.000")).quantize(Decimal("0.001")))
            row.summary = summary
            row.save(update_fields=["summary"])


class Migration(migrations.Migration):
    dependencies = [
        ("dayclose", "0005_purchase_money"),
    ]

    operations = [
        migrations.RunPython(split, migrations.RunPython.noop),
    ]
