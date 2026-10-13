from django.db import migrations
from django.db.models import OuterRef, Subquery


def end_closed_days(apps, schema_editor):  # type: ignore[no-untyped-def]
    """A day whose closing was already sent is over (D-134): it ends when the closing was sent."""
    DriverDay = apps.get_model("fleet", "DriverDay")
    DayClosing = apps.get_model("dayclose", "DayClosing")
    sent = DayClosing.objects.filter(driver_day_id=OuterRef("pk")).values("submitted_at")[:1]
    DriverDay.objects.filter(closing__isnull=False, ended_at__isnull=True).update(ended_at=Subquery(sent))


class Migration(migrations.Migration):
    dependencies = [
        ("dayclose", "0002_sync_problems"),
        ("fleet", "0004_driver_day_number"),
    ]

    operations = [migrations.RunPython(end_closed_days, migrations.RunPython.noop)]
