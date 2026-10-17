from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0008_load_per_client"),
    ]

    operations = [
        migrations.AddField(
            model_name="transfer",
            name="from_cold_rooms",
            field=models.BooleanField(default=False),
        ),
    ]
