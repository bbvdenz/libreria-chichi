import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'websistemasinfo.settings')
django.setup()

from LibreriaChichi.models import Producto

# Prefijo de SKU según la categoría del producto
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


def prefijo_para(categoria):
    cat = (categoria or '').strip().upper()
    if cat in PREFIJOS:
        return PREFIJOS[cat]
    # Si la categoría no está en la lista, usa sus 3 primeras letras
    letras = ''.join(c for c in cat if c.isalpha())
    return (letras[:3] or 'GEN').upper()


def generar_skus():
    print("⏳ Buscando productos sin SKU...")

    # Solo los que NO tienen SKU (null o vacío)
    productos = Producto.objects.filter(sku__isnull=True) | Producto.objects.filter(sku='')
    productos = productos.distinct()

    # SKUs ya usados, para no repetir
    usados = set(
        Producto.objects.exclude(sku__isnull=True)
        .exclude(sku='')
        .values_list('sku', flat=True)
    )

    if not productos.exists():
        print("✅ Todos los productos ya tienen SKU. No hay nada que hacer.")
        return

    contador = 0
    for prod in productos:
        prefijo = prefijo_para(prod.categoria)
        sku = f"{prefijo}-{prod.id_producto:04d}"

        # Por si acaso ya existiera ese SKU, le sumamos un sufijo
        base = sku
        n = 1
        while sku in usados:
            sku = f"{base}-{n}"
            n += 1

        prod.sku = sku
        prod.save(update_fields=['sku'])
        usados.add(sku)
        contador += 1
        print(f"🏷️  {prod.nombre_producto}  ->  {sku}")

    print(f"🎉 ¡Listo! Se generó SKU para {contador} producto(s).")


if __name__ == '__main__':
    generar_skus()
