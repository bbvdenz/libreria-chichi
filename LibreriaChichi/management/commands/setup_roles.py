from django.core.management.base import BaseCommand

from LibreriaChichi.permisos import configurar_roles


class Command(BaseCommand):
    help = "Crea/actualiza los grupos de roles (Administrador, Cajero, Bodeguero) y sus permisos."

    def handle(self, *args, **options):
        self.stdout.write("Configurando roles de la librería...")
        configurar_roles(verbose=True)
        self.stdout.write(self.style.SUCCESS("✔ Roles y permisos configurados correctamente."))
