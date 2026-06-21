from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('LibreriaChichi', '0006_producto_imagen_url_larga'),
    ]

    operations = [
        migrations.AlterField(
            model_name='producto',
            name='imagen',
            field=models.TextField(blank=True, null=True),
        ),
    ]
