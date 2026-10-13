from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fleet", "0003_driver_days"),
    ]

    operations = [
        migrations.AddField(
            model_name="driverday",
            name="ended_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
