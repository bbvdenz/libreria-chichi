"""
subir_imagenes_faltantes.py
===========================
Sube las imágenes faltantes a Cloudinary y guarda la URL en la BD de Azure.
Busca cada imagen DENTRO de "Fotos Pagina" (en todas sus subcarpetas),
así da igual en qué subcarpeta la hayas dejado.

CÓMO USARLO (en el CMD, en la raíz del proyecto):
    set DBHOST=chichi-db.postgres.database.azure.com
    set DBNAME=bdd_sisinfo
    set DBUSER=chichiadmin
    set DBPASS=Db2024!Xqz
    python subir_imagenes_faltantes.py
"""

import os, sys, django

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'websistemasinfo.settings')
django.setup()

import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name="dof5bbre5",
    api_key="843477436781424",
    api_secret="2HA7Cf-3Xr1NjPxu4OoL4kVbp9s",
    secure=True,
)

# Carpeta donde buscar (y todas sus subcarpetas)
RAIZ_BUSQUEDA = os.path.join(BASE, "Fotos Pagina")

# Producto en la BD  →  nombre del archivo (tal como lo guardaste)
MAPA = {
    "Transportador 180°":            "Transportador 180°",
    "Compás escolar":                "Compás escolar",
    "Regla 20cm":                    "Regla 20cm",
    "Regla 30cm":                    "Regla 30cm",
    "Set Limpiapipas / Limpieza":    "Set Limpiapipas  Limpieza",
    "Bastidor para pintar":          "Bastidor para pintar",
    "Resma de Papel Carta 500 hjs":  "Resma de Papel Carta 500 hjs",
    "Block Paño Lenci":              "Block Paño Lenci",
    "Block Cartulina Española":      "Block Cartulina Española",
    "Plastilina escolar":            "Plastilina escolar",
    "Pintura acrílica suelta":       "Pintura acrílica suelta",
}

EXTS = (".png", ".jpg", ".jpeg", ".webp")

def buscar_archivo(nombre_sin_ext):
    """Busca un archivo por nombre (sin extensión) dentro de Fotos Pagina,
    en todas las subcarpetas, ignorando mayúsculas."""
    objetivo = nombre_sin_ext.lower()
    for carpeta, _dirs, archivos in os.walk(RAIZ_BUSQUEDA):
        for f in archivos:
            base, ext = os.path.splitext(f)
            if ext.lower() in EXTS and base.lower() == objetivo:
                return os.path.join(carpeta, f)
    return None

from LibreriaChichi.models import Producto
from django.db import connection

total, ok, errores = len(MAPA), 0, []
print(f"\n🚀 Subiendo {total} imágenes a Cloudinary...\n")

if not os.path.isdir(RAIZ_BUSQUEDA):
    print(f"❌ No encuentro la carpeta '{RAIZ_BUSQUEDA}'.")
    print("   Asegúrate de correr el script en la raíz del proyecto.")
    sys.exit(1)

for nombre_prod, archivo_base in MAPA.items():
    ruta = buscar_archivo(archivo_base)
    if not ruta:
        print(f"  ⚠️  No encontré el archivo '{archivo_base}' dentro de Fotos Pagina")
        errores.append(nombre_prod)
        continue

    prod = Producto.objects.filter(nombre_producto=nombre_prod).first()
    if not prod:
        print(f"  ⚠️  Producto no está en la BD: {nombre_prod!r}")
        errores.append(nombre_prod)
        continue

    try:
        public_id = "chichi/" + "".join(
            c if c.isalnum() else "_" for c in nombre_prod.lower()
        ).strip("_")
        resultado = cloudinary.uploader.upload(
            ruta,
            public_id=public_id,
            overwrite=True,
            resource_type="image",
            transformation=[{"width": 800, "height": 800, "crop": "limit", "quality": "auto"}],
        )
        url = resultado["secure_url"]
        with connection.cursor() as c:
            c.execute(
                "UPDATE producto SET imagen = %s WHERE id_producto = %s",
                [url, prod.id_producto]
            )
        ok += 1
        print(f"  ✅ [{ok}/{total}] {nombre_prod}")
    except Exception as e:
        print(f"  ❌ Error con {nombre_prod!r}: {e}")
        errores.append(nombre_prod)

print(f"\n{'='*50}")
print(f"✅ Subidas: {ok}/{total}")
if errores:
    print(f"⚠️  Con problemas: {', '.join(errores)}")
print("="*50)
print("\n¡Listo! Recarga el catálogo (Ctrl+Shift+R) y verás las fotos. 🎉\n")
