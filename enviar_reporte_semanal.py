"""
Reporte semanal de ventas de Librería Chichi (script de respaldo).

Envía por correo el reporte de la semana actual con el Excel adjunto.
El destinatario se toma de settings.REPORTE_EMAIL (configúralo con la
variable de entorno REPORTE_EMAIL; si no, cae al correo de envío).

Uso (entorno activado, dentro de websistemasinfo):
    python enviar_reporte_semanal.py

Nota: para el envío AUTOMÁTICO cada semana no necesitas este script.
Usa el botón del panel de Ventas, o el endpoint:
    /gestion/reporte/enviar/?token=<REPORTE_TOKEN>
llamado por un programador externo (ver instrucciones). Este script queda
como respaldo por si quieres dispararlo a mano o desde el Programador de
tareas de Windows.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'websistemasinfo.settings')
django.setup()

from django.conf import settings
from LibreriaChichi.reportes import enviar_reporte_correo


def main():
    destino = getattr(settings, 'REPORTE_EMAIL', '') or getattr(settings, 'DEFAULT_FROM_EMAIL', '')
    ok = enviar_reporte_correo(destino)
    if not ok:
        print("No se pudo enviar el reporte (revisa REPORTE_EMAIL y la config SMTP).")


if __name__ == '__main__':
    main()
