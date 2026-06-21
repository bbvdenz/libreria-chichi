from django.db import migrations

class Migration(migrations.Migration):
    """
    Amplía el campo 'imagen' de producto a TEXT para soportar
    URLs largas de Cloudinary (que superan los 100 caracteres del ImageField).
    """

    dependencies = [
        ('LibreriaChichi', '0005_producto_activo'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE producto ALTER COLUMN imagen TYPE TEXT;",
            reverse_sql="ALTER TABLE producto ALTER COLUMN imagen TYPE VARCHAR(100);",
        ),
    ]
