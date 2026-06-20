"""
Carga el catálogo completo de la Librería Chichi en la base de datos.

A diferencia del cargador antiguo, este script asigna a cada producto:
  • su CATEGORÍA correcta (para que el filtro por secciones funcione),
  • un SKU correlativo por categoría (PIN-001, PAP-001, ...),
  • un registro de Stock inicial.

Es idempotente: si vuelves a correrlo, no duplica productos; solo completa
lo que falte (categoría, SKU o stock).

Uso:
    python cargar_catalogo_completo.py
"""
import os
import re
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'websistemasinfo.settings')
django.setup()

from LibreriaChichi.models import Producto, Stock

# Stock inicial para productos nuevos (ajústalo o usa cargar_stock.py luego).
STOCK_INICIAL = 10

PREFIJOS = {
    'PINTURA Y COLOR': 'PIN',
    'PAPEL Y CARTULINA': 'PAP',
    'CUADERNOS Y FORROS': 'CUA',
    'LAPICES Y ESCRITURA': 'LAP',
    'GEOMETRIA': 'GEO',
    'ADHESIVOS Y PEGAMENTOS': 'ADH',
    'MANUALIDADES': 'MAN',
    'CARPETERIA': 'CAR',
    'OTROS': 'OTR',
}

# (nombre, precio, categoría) — categorías idénticas a las del filtro del sitio.
CATALOGO = [
    # ── PINTURA Y COLOR ──
    ("Acrílicos 12 colores", 3490, "PINTURA Y COLOR"),
    ("Acrílicos 36 colores", 7990, "PINTURA Y COLOR"),
    ("Acrílicos 48 colores", 11990, "PINTURA Y COLOR"),
    ("Acrílicos 60 colores", 14990, "PINTURA Y COLOR"),
    ("Acrílicos 80 colores", 19990, "PINTURA Y COLOR"),
    ("Acuarela en pastilla", 2490, "PINTURA Y COLOR"),
    ("Pintura acrílica suelta", 1290, "PINTURA Y COLOR"),
    ("Témpera 12 colores", 1690, "PINTURA Y COLOR"),
    ("Témpera 250 ml", 1990, "PINTURA Y COLOR"),
    ("Témpera metálica 6 colores", 2190, "PINTURA Y COLOR"),
    ("Set témpera sólida 12 colores", 4290, "PINTURA Y COLOR"),
    ("Set témpera escolar", 1490, "PINTURA Y COLOR"),
    ("Plastilina escolar", 990, "PINTURA Y COLOR"),
    ("Masa DAS 500g", 3290, "PINTURA Y COLOR"),
    ("Masita Gummy x12", 1990, "PINTURA Y COLOR"),
    ("Masita Gummy x24", 3490, "PINTURA Y COLOR"),
    ("Masita Gummy x36", 4990, "PINTURA Y COLOR"),

    # ── PAPEL Y CARTULINA ──
    ("Block Papel Entretenido", 1490, "PAPEL Y CARTULINA"),
    ("Block Cartulina", 1290, "PAPEL Y CARTULINA"),
    ("Block Cartulina Escarchada", 1990, "PAPEL Y CARTULINA"),
    ("Block Cartulina Española", 1690, "PAPEL Y CARTULINA"),
    ("Block de Cartulina Metálica", 1890, "PAPEL Y CARTULINA"),
    ("Block Dibujo 99 1/8", 1690, "PAPEL Y CARTULINA"),
    ("Block Paño Lenci", 2490, "PAPEL Y CARTULINA"),
    ("Block Papel Lustre", 890, "PAPEL Y CARTULINA"),
    ("Cartulina en pliego", 350, "PAPEL Y CARTULINA"),
    ("Papel Celofán (pliego)", 450, "PAPEL Y CARTULINA"),
    ("Papel Crepé", 390, "PAPEL Y CARTULINA"),
    ("Papel Lustre 10x10", 490, "PAPEL Y CARTULINA"),
    ("Papel Lustre 16x16", 790, "PAPEL Y CARTULINA"),
    ("Papel Volantín", 250, "PAPEL Y CARTULINA"),
    ("Resma de Papel Carta 500 hjs", 4990, "PAPEL Y CARTULINA"),
    ("Croquera Acuarela", 3990, "PAPEL Y CARTULINA"),
    ("Croquera Dibujo", 2490, "PAPEL Y CARTULINA"),
    ("Papel Kraft (pliego)", 400, "PAPEL Y CARTULINA"),

    # ── CUADERNOS Y FORROS ──
    ("Cuaderno Collage 5mm 100 hjs", 1490, "CUADERNOS Y FORROS"),
    ("Cuaderno Collage 7mm 100 hjs", 1490, "CUADERNOS Y FORROS"),
    ("Cuaderno Croquis", 1690, "CUADERNOS Y FORROS"),
    ("Cuaderno Universitario 7mm 100 hjs", 1890, "CUADERNOS Y FORROS"),
    ("Forros Collage (unidad)", 250, "CUADERNOS Y FORROS"),
    ("Forros Universitarios (unidad)", 300, "CUADERNOS Y FORROS"),

    # ── LAPICES Y ESCRITURA ──
    ("Lápices Bicolor (pack)", 990, "LAPICES Y ESCRITURA"),
    ("Lápices de Colores x12", 1990, "LAPICES Y ESCRITURA"),
    ("Lápices Grafito (pack 4)", 1290, "LAPICES Y ESCRITURA"),
    ("Lápiz Mina 0.5", 890, "LAPICES Y ESCRITURA"),
    ("Lápiz Mina 0.3", 990, "LAPICES Y ESCRITURA"),
    ("Lápiz Pasta (Bic/Torre)", 350, "LAPICES Y ESCRITURA"),
    ("Lápices Scripto x12", 1890, "LAPICES Y ESCRITURA"),
    ("Lápices Scripto Glitter", 2990, "LAPICES Y ESCRITURA"),
    ("Lápiz Grafito suelto", 250, "LAPICES Y ESCRITURA"),
    ("Minas 0.5", 450, "LAPICES Y ESCRITURA"),
    ("Minas 0.7", 450, "LAPICES Y ESCRITURA"),
    ("Goma de borrar", 300, "LAPICES Y ESCRITURA"),
    ("Destacadores (unidad)", 690, "LAPICES Y ESCRITURA"),
    ("Corrector en cinta / líquido", 990, "LAPICES Y ESCRITURA"),
    ("Sacapuntas con depósito", 590, "LAPICES Y ESCRITURA"),

    # ── GEOMETRIA ──
    ("Regla 20cm", 400, "GEOMETRIA"),
    ("Regla 30cm", 600, "GEOMETRIA"),
    ("Compás escolar", 1490, "GEOMETRIA"),
    ("Transportador 180°", 350, "GEOMETRIA"),

    # ── ADHESIVOS Y PEGAMENTOS ──
    ("Cinta doble faz", 1290, "ADHESIVOS Y PEGAMENTOS"),
    ("Cinta Embalaje", 1490, "ADHESIVOS Y PEGAMENTOS"),
    ("Cinta Papel Grueso (masking)", 1390, "ADHESIVOS Y PEGAMENTOS"),
    ("Cola fría 500 grs", 2990, "ADHESIVOS Y PEGAMENTOS"),
    ("Silicona Líquida 250ml", 2190, "ADHESIVOS Y PEGAMENTOS"),
    ("Pegamento en barra 115g", 2490, "ADHESIVOS Y PEGAMENTOS"),
    ("Pegamento en barra 21g", 990, "ADHESIVOS Y PEGAMENTOS"),
    ("Pegamento en barra 36g", 1490, "ADHESIVOS Y PEGAMENTOS"),

    # ── MANUALIDADES (Goma Eva + manualidades) ──
    ("Goma Eva con Glitter (pliego chico)", 550, "MANUALIDADES"),
    ("Goma Eva en pliego grande Glitter", 1390, "MANUALIDADES"),
    ("Goma Eva en pliego grande normal", 990, "MANUALIDADES"),
    ("Goma Eva sin Glitter (chica)", 300, "MANUALIDADES"),
    ("Barras de Silicona (unidad)", 150, "MANUALIDADES"),
    ("Bastidor para pintar", 2490, "MANUALIDADES"),
    ("Palos de helado colores (pack)", 990, "MANUALIDADES"),
    ("Palos de helado grueso (pack)", 1190, "MANUALIDADES"),
    ("Palos de helado natural (pack)", 790, "MANUALIDADES"),
    ("Set Escarcha / Brillantina", 1290, "MANUALIDADES"),
    ("Set Brochas de espuma", 1990, "MANUALIDADES"),
    ("Set Pinceles económicos", 2490, "MANUALIDADES"),
    ("Set Limpiapipas / Limpieza", 1190, "MANUALIDADES"),
    ("Mezclador de pintura", 490, "MANUALIDADES"),
    ("Tijeras punta roma escolar", 890, "MANUALIDADES"),
    ("Tijeras grandes punta fina", 1890, "MANUALIDADES"),
    ("Tijeras grandes punta normal", 1690, "MANUALIDADES"),

    # ── CARPETERIA ──
    ("Carpeta Acolchada", 2190, "CARPETERIA"),
    ("Carpeta Estuche con cierre", 1590, "CARPETERIA"),

    # ── OTROS (calculadoras + plumones) ──
    ("Calculadora Normal de escritorio", 3990, "OTROS"),
    ("Calculadora Científica estándar", 9990, "OTROS"),
    ("Plumón Permanente (Negro/Azul/Rojo)", 790, "OTROS"),
    ("Plumón Pizarra", 890, "OTROS"),
]


def prefijo_para(categoria):
    cat = (categoria or '').strip().upper()
    if cat in PREFIJOS:
        return PREFIJOS[cat]
    letras = ''.join(c for c in cat if c.isalpha())
    return (letras[:3] or 'GEN').upper()


def siguiente_sku(categoria, usados):
    """SKU correlativo por categoría, p.ej. 'PIN-001'. Evita choques."""
    prefijo = prefijo_para(categoria)
    maximo = 0
    for s in usados:
        if s and s.startswith(prefijo + '-'):
            m = re.search(r'-(\d+)', s)
            if m:
                maximo = max(maximo, int(m.group(1)))
    n = maximo + 1
    sku = f"{prefijo}-{n:03d}"
    while sku in usados:
        n += 1
        sku = f"{prefijo}-{n:03d}"
    return sku


def cargar():
    print("⏳ Cargando catálogo completo (categoría + SKU + stock)...")

    # SKUs ya usados en la BD, para no repetir
    usados = set(
        Producto.objects.exclude(sku__isnull=True).exclude(sku='')
        .values_list('sku', flat=True)
    )

    nuevos = actualizados = stock_creado = 0

    for nombre, precio, categoria in CATALOGO:
        prod = Producto.objects.filter(nombre_producto=nombre).first()

        if prod is None:
            prod = Producto.objects.create(
                nombre_producto=nombre,
                precio=precio,
                categoria=categoria,
                activo=True,
            )
            nuevos += 1
            print(f"✅ Nuevo: {nombre}  [{categoria}]  ${precio}")
        else:
            cambios = []
            if (prod.categoria or '').strip().upper() != categoria:
                prod.categoria = categoria
                cambios.append("categoría")
            if not prod.precio or float(prod.precio) == 0:
                prod.precio = precio
                cambios.append("precio")
            if cambios:
                prod.save()
                actualizados += 1
                print(f"♻️  Actualizado ({', '.join(cambios)}): {nombre}")

        # SKU si falta
        if not prod.sku:
            sku = siguiente_sku(categoria, usados)
            prod.sku = sku
            prod.save(update_fields=['sku'])
            usados.add(sku)
            print(f"   🏷️  SKU: {sku}")

        # Stock inicial si falta
        _, creado = Stock.objects.get_or_create(
            id_producto=prod,
            defaults={'cantidad_disponible': STOCK_INICIAL},
        )
        if creado:
            stock_creado += 1

    print("\n🎉 Listo.")
    print(f"   • Productos nuevos:      {nuevos}")
    print(f"   • Productos actualizados:{actualizados}")
    print(f"   • Registros de stock:    {stock_creado}")
    print(f"   • Total en catálogo:     {Producto.objects.count()}")


if __name__ == '__main__':
    cargar()
