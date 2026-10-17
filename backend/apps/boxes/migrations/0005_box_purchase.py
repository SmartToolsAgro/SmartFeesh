from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('boxes', '0004_made_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='boxmovement',
            name='kind',
            field=models.CharField(choices=[('opening', 'Stock initial'), ('receive', 'Réception fournisseur'), ('load', 'Chargement camion'), ('leave', 'Départ chez client'), ('collect', 'Reprise chez client'), ('return', 'Retour fournisseur'), ('truck_return', 'Retour du camion en chambre froide'), ('write_off', 'Casse ou perte'), ('purchase', 'Achat de caisses')], max_length=12),
        ),
    ]
