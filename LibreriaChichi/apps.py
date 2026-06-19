from django.apps import AppConfig


class LibreriachichiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'LibreriaChichi'

    def ready(self):
        # Crear/actualizar los grupos de roles automáticamente después de
        # cada `migrate` (patrón recomendado por Django para datos iniciales).
        from django.db.models.signals import post_migrate
        post_migrate.connect(_crear_roles_post_migrate, sender=self)


def _crear_roles_post_migrate(sender, **kwargs):
    # Import tardío para evitar tocar la BD al importar el módulo.
    try:
        from .permisos import configurar_roles
        configurar_roles(verbose=False)
    except Exception as e:  # nunca romper el migrate por esto
        print(f"[roles] aviso: no se pudieron configurar los grupos aún: {e}")
