import os
import django
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'websistemasinfo.settings')
django.setup()

from LibreriaChichi.models import Producto, Stock

def asignar_stock_aleatorio():
    print("⏳ Buscando productos para asignarles stock al azar...")
    
    productos = Producto.objects.all()
    
    if not productos.exists():
        print("❌ No hay productos en la base de datos. Recuerda correr primero el del catálogo.")
        return

    contador = 0
    for prod in productos:
        cantidad_al_azar = random.randint(1, 14)
        
        stock_registro, created = Stock.objects.get_or_create(
            id_producto=prod,  # <-- Nombre real de la llave foránea
            defaults={
                'cantidad_disponible': cantidad_al_azar  # <-- Nombre real del campo numérico
            }
        )
        
        if created:
            print(f"📦 Stock asignado: {prod.nombre_producto} -> {cantidad_al_azar} unidades.")
            contador += 1
        else:
            print(f"⚠️ {prod.nombre_producto} ya tenía un registro en la tabla Stocks.")

    print(f"🎉 ¡Proceso terminado! Se actualizaron {contador} registros en la tabla Stocks.")

if __name__ == '__main__':
    assign_stock_aleatorio = asignar_stock_aleatorio()