from django.db import migrations


def seed_kilogram(apps, schema_editor):
    Unit = apps.get_model("catalog", "Unit")
    Unit.objects.get_or_create(code="kg", defaults={"name": "Kilogramme", "symbol": "kg"})


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
    ]

    # Going back leaves the row: products may point to it, and 0001 drops the table anyway.
    operations = [
        migrations.RunPython(seed_kilogram, migrations.RunPython.noop),
    ]
