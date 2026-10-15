from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_jobrun"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="real_data_since",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
