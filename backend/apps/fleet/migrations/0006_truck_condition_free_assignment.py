from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0005_purchase_float'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='truck',
            name='condition',
            field=models.CharField(choices=[('ok', 'En service'), ('maintenance', 'En maintenance'), ('breakdown', 'En panne')], default='ok', max_length=12),
        ),
        migrations.AlterField(
            model_name='truckassignment',
            name='driver',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='truck_assignments', to=settings.AUTH_USER_MODEL),
        ),
    ]
