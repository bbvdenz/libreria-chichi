"""
subir_fotos_cloudinary.py
=========================
Sube las fotos de productos a Cloudinary y actualiza la BD de Azure.

CÓMO USARLO
-----------
1. Pon este script en la raíz de tu proyecto
   (junto a manage.py y la carpeta "Fotos Pagina")

2. En el CMD corre (con tus datos de Azure):
      set DBHOST=chichi-db.postgres.database.azure.com
      set DBNAME=bdd_sisinfo
      set DBUSER=chichiadmin
      set DBPASS=Db2024!Xqz
      python subir_fotos_cloudinary.py
"""

import os, sys, django

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'websistemasinfo.settings')
django.setup()

import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name = "dof5bbre5",
    api_key    = "843477436781424",
    api_secret = "2HA7Cf-3Xr1NjPxu4OoL4kVbp9s",
    secure     = True,
)

F = "Fotos Pagina"
MAPA = {
    "Acrílicos 12 colores":                    f"{F}/Pintura y color/Acrilicos-_12-Colores_1.png",
    "Acrílicos 36 colores":                    f"{F}/Pintura y color/acrilicos 36.png",
    "Acrílicos 48 colores":                    f"{F}/Pintura y color/acrilicos set-48-colores-.png",
    "Acrílicos 60 colores":                    f"{F}/Pintura y color/acrilicos 60.png",
    "Acrílicos 80 colores":                    f"{F}/Pintura y color/acrilicos-80.png",
    "Acuarela en pastilla":                    f"{F}/Pintura y color/acuarela-campus-28-pastillas.png",
    "Témpera 12 colores":                      f"{F}/Pintura y color/Tempera-12-Colores-Artel.png",
    "Témpera 250 ml":                          f"{F}/Pintura y color/Tempera-250ml.png",
    "Témpera metálica 6 colores":              f"{F}/Pintura y color/Tempera-12-Colores-Artel.png",
    "Set témpera sólida 12 colores":           f"{F}/Pintura y color/Tempera-Solida.png",
    "Set témpera escolar":                     f"{F}/Pintura y color/set-tempera.png",
    "Masa DAS 500g":                           f"{F}/Pintura y color/masa-das.png",
    "Masita Gummy x12":                        f"{F}/Pintura y color/masita-gummy-12.png",
    "Masita Gummy x24":                        f"{F}/Pintura y color/masita-gummy-12.png",
    "Masita Gummy x36":                        f"{F}/Pintura y color/masita-gummy-12.png",
    "Block Papel Entretenido":                 f"{F}/Papel, cartulina y blocks/mabeduna-papel-entretenido-torre-01-01.jpg",
    "Block Cartulina":                         f"{F}/Papel, cartulina y blocks/cartulina.png",
    "Block Cartulina Escarchada":              f"{F}/Papel, cartulina y blocks/block cartulina escarchada.png",
    "Block de Cartulina Metálica":             f"{F}/Papel, cartulina y blocks/cartulina metalica.jpg",
    "Block Dibujo 99 1/8":                    f"{F}/Papel, cartulina y blocks/block dibujo 99.png",
    "Block Papel Lustre":                      f"{F}/Papel, cartulina y blocks/block papel lustre.png",
    "Cartulina en pliego":                     f"{F}/Papel, cartulina y blocks/pliego cartulina.png",
    "Papel Celofán (pliego)":                  f"{F}/Papel, cartulina y blocks/papel celofan.png",
    "Papel Crepé":                             f"{F}/Papel, cartulina y blocks/papel crepe.png",
    "Papel Lustre 10x10":                      f"{F}/Papel, cartulina y blocks/papel lustre 10x10.png",
    "Papel Lustre 16x16":                      f"{F}/Papel, cartulina y blocks/papel lustre 16x16.png",
    "Papel Volantín":                          f"{F}/Papel, cartulina y blocks/papel volantin.JPG",
    "Croquera Acuarela":                       f"{F}/Papel, cartulina y blocks/croquera acuarela.png",
    "Croquera Dibujo":                         f"{F}/Papel, cartulina y blocks/croquera dibujo.png",
    "Papel Kraft (pliego)":                    f"{F}/Papel, cartulina y blocks/papel-kraft.png",
    "Cuaderno Collage 5mm 100 hjs":            f"{F}/Cuadernos y forros/Cuadernos collage 5mm.png",
    "Cuaderno Collage 7mm 100 hjs":            f"{F}/Cuadernos y forros/cuadernos collage 7mm.png",
    "Cuaderno Croquis":                        f"{F}/Cuadernos y forros/Cuaderno croquis.png",
    "Cuaderno Universitario 7mm 100 hjs":      f"{F}/Cuadernos y forros/Cuaderno universitario.png",
    "Forros Collage (unidad)":                 f"{F}/Cuadernos y forros/Forros collage.png",
    "Forros Universitarios (unidad)":          f"{F}/Cuadernos y forros/Forros universitarios.png",
    "Lápices Bicolor (pack)":                  f"{F}/Lapices, minas, gomas/Lapices de colores.png",
    "Lápices de Colores x12":                  f"{F}/Lapices, minas, gomas/Lapices de colores.png",
    "Lápices Grafito (pack 4)":                f"{F}/Lapices, minas, gomas/lapices grafito.png",
    "Lápiz Mina 0.5":                          f"{F}/Lapices, minas, gomas/Porta mina 0,5.png",
    "Lápiz Mina 0.3":                          f"{F}/Lapices, minas, gomas/Porta mina 0,5.png",
    "Lápiz Pasta (Bic/Torre)":                 f"{F}/Lapices, minas, gomas/lapices pasta.png",
    "Lápices Scripto x12":                     f"{F}/Lapices, minas, gomas/Lapices scripto.png",
    "Lápices Scripto Glitter":                 f"{F}/Lapices, minas, gomas/Lapices scripto glitter.png",
    "Lápiz Grafito suelto":                    f"{F}/Lapices, minas, gomas/Lapiz grafito suelto.png",
    "Minas 0.5":                               f"{F}/Lapices, minas, gomas/Minas 0,5.png",
    "Minas 0.7":                               f"{F}/Lapices, minas, gomas/Minas 0,7.png",
    "Goma de borrar":                          f"{F}/Lapices, minas, gomas/Goma de borrar.png",
    "Destacadores (unidad)":                   f"{F}/Lapices, minas, gomas/Destacadores.png",
    "Corrector en cinta / líquido":            f"{F}/Lapices, minas, gomas/Corrector.png",
    "Sacapuntas con depósito":                 f"{F}/Lapices, minas, gomas/Saca puntas.png",
    "Cinta doble faz":                         f"{F}/Adhesivos, siliconas y pegamentos/cinta doble fasz.png",
    "Cinta Embalaje":                          f"{F}/Adhesivos, siliconas y pegamentos/Cinta embalaje.png",
    "Cinta Papel Grueso (masking)":            f"{F}/Adhesivos, siliconas y pegamentos/Cinta papel grueso.png",
    "Cola fría 500 grs":                       f"{F}/Adhesivos, siliconas y pegamentos/cola fria 500gr.png",
    "Silicona Líquida 250ml":                  f"{F}/Adhesivos, siliconas y pegamentos/silicona liquida.png",
    "Pegamento en barra 115g":                 f"{F}/Adhesivos, siliconas y pegamentos/pegamento en barra 115gr.png",
    "Pegamento en barra 21g":                  f"{F}/Adhesivos, siliconas y pegamentos/pegamento en barra 21gr.png",
    "Pegamento en barra 36g":                  f"{F}/Adhesivos, siliconas y pegamentos/pegamento en barra 36g.png",
    "Goma Eva con Glitter (pliego chico)":     f"{F}/Goma eva y manualidades/Goma Eva Glitter.png",
    "Goma Eva en pliego grande Glitter":       f"{F}/Goma eva y manualidades/Goma eva pliego glitter.png",
    "Goma Eva en pliego grande normal":        f"{F}/Goma eva y manualidades/Goma eva pliego normal.png",
    "Goma Eva sin Glitter (chica)":            f"{F}/Goma eva y manualidades/Goma eva.png",
    "Barras de Silicona (unidad)":             f"{F}/Goma eva y manualidades/Barras de silicona.png",
    "Palos de helado colores (pack)":          f"{F}/Goma eva y manualidades/palos de helado color.png",
    "Palos de helado grueso (pack)":           f"{F}/Goma eva y manualidades/Palos helado grueso.png",
    "Palos de helado natural (pack)":          f"{F}/Goma eva y manualidades/palitos helado natural.png",
    "Set Escarcha / Brillantina":              f"{F}/Goma eva y manualidades/escarchas.png",
    "Set Brochas de espuma":                   f"{F}/Goma eva y manualidades/set brochas.png",
    "Set Pinceles económicos":                 f"{F}/Goma eva y manualidades/Set de pinceles.png",
    "Mezclador de pintura":                    f"{F}/Goma eva y manualidades/Mezclador.png",
    "Tijeras punta roma escolar":              f"{F}/Goma eva y manualidades/Tijeras punta roma.png",
    "Tijeras grandes punta fina":              f"{F}/Goma eva y manualidades/Tijera punta fina.png",
    "Tijeras grandes punta normal":            f"{F}/Goma eva y manualidades/Tijeras normal.png",
    "Carpeta Acolchada":                       f"{F}/carpeta y estuche/carpeta acolchada.png",
    "Carpeta Estuche con cierre":              f"{F}/carpeta y estuche/carpeta estuche.png",
    "Calculadora Normal de escritorio":        f"{F}/calculadoras/calculadora normal.png",
    "Calculadora Científica estándar":         f"{F}/calculadoras/calculadora cientifica.png",
    "Plumón Pizarra":                          f"{F}/Plumones/plumones pizarra.png",
    "Plumón Permanente (Negro/Azul/Rojo)":     f"{F}/Plumones/Plumones permanentes.png",
}

from LibreriaChichi.models import Producto
from django.db import connection

total   = len(MAPA)
subidos = 0
errores = []

print(f"\n🚀 Subiendo {total} fotos a Cloudinary...\n")

for nombre_prod, ruta_relativa in MAPA.items():
    ruta = os.path.join(BASE, ruta_relativa)

    # Buscar ignorando mayúsculas (útil en Windows)
    if not os.path.exists(ruta):
        carpeta = os.path.dirname(ruta)
        archivo = os.path.basename(ruta)
        if os.path.isdir(carpeta):
            for f in os.listdir(carpeta):
                if f.lower() == archivo.lower():
                    ruta = os.path.join(carpeta, f)
                    break

    if not os.path.exists(ruta):
        print(f"  ⚠️  Archivo no encontrado: {ruta_relativa}")
        errores.append(nombre_prod)
        continue

    prod = Producto.objects.filter(nombre_producto=nombre_prod).first()
    if not prod:
        print(f"  ⚠️  Producto no encontrado en BD: {nombre_prod!r}")
        errores.append(nombre_prod)
        continue

    try:
        # public_id corto: solo letras/números/guiones (cabe en varchar 100)
        public_id = "chichi/" + "".join(
            c if c.isalnum() else "_"
            for c in nombre_prod.lower()
        ).strip("_")

        resultado = cloudinary.uploader.upload(
            ruta,
            public_id     = public_id,
            overwrite     = True,
            resource_type = "image",
        )

        # Guardamos la URL segura directamente con SQL para evitar el límite del campo
        url = resultado["secure_url"]
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE producto SET imagen = %s WHERE id_producto = %s",
                [url, prod.id_producto]
            )

        subidos += 1
        print(f"  ✅ [{subidos}/{total}] {nombre_prod}")

    except Exception as e:
        print(f"  ❌ Error con {nombre_prod!r}: {e}")
        errores.append(nombre_prod)

print(f"\n{'='*50}")
print(f"✅ Subidos: {subidos}/{total}")
if errores:
    print(f"⚠️  Con problemas ({len(errores)}): {', '.join(errores[:5])}{'...' if len(errores)>5 else ''}")
print("="*50)
print("\n¡Listo! Entra al catálogo y verás todas las fotos. 🎉\n")
