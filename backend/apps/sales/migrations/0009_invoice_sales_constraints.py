from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('sales', '0008_invoice_sales')]

    operations = [
        migrations.RemoveField(
            model_name='invoice',
            name='sale',
        ),
        migrations.AddField(
            model_name='invoice',
            name='sales',
            field=models.ManyToManyField(related_name='invoices', through='sales.InvoiceSale', to='sales.sale'),
        ),
        migrations.AddConstraint(
            model_name='invoicesale',
            constraint=models.UniqueConstraint(fields=('invoice', 'sale'), name='one_row_per_invoice_and_sale'),
        ),
        migrations.AddConstraint(
            model_name='invoicesale',
            constraint=models.UniqueConstraint(condition=models.Q(('is_live', True)), fields=('sale',), name='one_live_invoice_per_sale'),
        ),
    ]
