from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("partnerships", "0002_settlement"),
    ]

    operations = [
        migrations.AddField(
            model_name="lotpartnership",
            name="terms_pending",
            field=models.BooleanField(default=False),
        ),
    ]
