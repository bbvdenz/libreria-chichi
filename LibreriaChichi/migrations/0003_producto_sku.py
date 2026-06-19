from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('LibreriaChichi', '0002_cliente_direccion_facturacion_cliente_rut_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='producto',
            name='sku',
            field=models.CharField(blank=True, max_length=40, null=True, unique=True),
        ),
    ]
