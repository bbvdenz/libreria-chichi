# Generated for soft-delete support (campo Producto.activo)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('LibreriaChichi', '0004_claveapi_transferencia'),
    ]

    operations = [
        migrations.AddField(
            model_name='producto',
            name='activo',
            field=models.BooleanField(default=True),
        ),
    ]
