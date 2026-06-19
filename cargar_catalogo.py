import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'websistemasinfo.settings')
django.setup()

from LibreriaChichi.models import Producto

def cargar_productos():
    inventario = [
        {"nombre": "Acrílicos 12 colores", "precio": 3490},
        {"nombre": "Acrílicos 36 colores", "precio": 7990},
        {"nombre": "Acrílicos 48 colores", "precio": 11990},
        {"nombre": "Acrílicos 60 colores", "precio": 14990},
        {"nombre": "Acrílicos 80 colores", "precio": 19990},
        {"nombre": "Acuarela en pastilla", "precio": 2490},
        {"nombre": "Pintura acrília suelta", "precio": 1290},
        {"nombre": "Témpera 12 colores", "precio": 1690},
        {"nombre": "Témpera 250 ml", "precio": 1990},
        {"nombre": "Témpera metálica 6 colores", "precio": 2190},
        {"nombre": "Set témpera sólida 12 colores", "precio": 4290},
        {"nombre": "Set témpera escolar", "precio": 1490},
        {"nombre": "Plastilina escolar", "precio": 990},
        {"nombre": "Masa DAS 500g", "precio": 3290},
        {"nombre": "Masita Gummy x12", "precio": 1990},
        {"nombre": "Masita Gummy x24", "precio": 3490},
        {"nombre": "Masita Gummy x36", "precio": 4990},

        {"nombre": "Block Papel Entretenido", "precio": 1490},
        {"nombre": "Block Cartulina", "precio": 1290},
        {"nombre": "Block Cartulina Escarchada", "precio": 1990},
        {"nombre": "Block Cartulina Española", "precio": 1690},
        {"nombre": "Block de Cartulina Metálica", "precio": 1890},
        {"nombre": "Block Dibujo 99 1/8", "precio": 1690},
        {"nombre": "Block Paño Lenci", "precio": 2490},
        {"nombre": "Block Papel Lustre", "precio": 890},
        {"nombre": "Cartulina en pliego", "precio": 350},
        {"nombre": "Papel Celofán (pliego)", "precio": 450},
        {"nombre": "Papel Crepé", "precio": 390},
        {"nombre": "Papel Lustre 10x10", "precio": 490},
        {"nombre": "Papel Lustre 16x16", "precio": 790},
        {"nombre": "Papel Volantín", "precio": 250},
        {"nombre": "Resma de Papel Carta 500 hjs", "precio": 4990},
        {"nombre": "Croquera Acuarela", "precio": 3990},
        {"nombre": "Croquera Dibujo", "precio": 2490},
        {"nombre": "Papel Kraft (pliego)", "precio": 400},

        {"nombre": "Cuaderno Collage 5mm 100 hjs", "precio": 1490},
        {"nombre": "Cuaderno Collage 7mm 100 hjs", "precio": 1490},
        {"nombre": "Cuaderno Croquis", "precio": 1690},
        {"nombre": "Cuaderno Universitario 7mm 100 hjs", "precio": 1890},
        {"nombre": "Forros Collage (unidad)", "precio": 250},
        {"nombre": "Forros Universitarios (unidad)", "precio": 300},

        {"nombre": "Lápices Bicolor (pack)", "precio": 990},
        {"nombre": "Lápices de Colores x12", "precio": 1990},
        {"nombre": "Lápices Grafito (pack 4)", "precio": 1290},
        {"nombre": "Lápiz Mina 0.5", "precio": 890},
        {"nombre": "Lápiz Mina 0.3", "precio": 990},
        {"nombre": "Lápiz Pasta (Bic/Torre)", "precio": 350},
        {"nombre": "Lápices Scripto x12", "precio": 1890},
        {"nombre": "Lápices Scripto Glitter", "precio": 2990},
        {"nombre": "Lápiz Grafito suelto", "precio": 250},
        {"nombre": "Minas 0.5", "precio": 450},
        {"nombre": "Minas 0.7", "precio": 450},
        {"nombre": "Goma de borrar", "precio": 300},
        {"nombre": "Destacadores (unidad)", "precio": 690},
        {"nombre": "Corrector en cinta / líquido", "precio": 990},
        {"nombre": "Sacapuntas con depósito", "precio": 590},

        {"nombre": "Regla 20cm", "precio": 400},
        {"nombre": "Regla 30cm", "precio": 600},
        {"nombre": "Compás escolar", "precio": 1490},
        {"nombre": "Transportador 180°", "precio": 350},

        {"nombre": "Cinta doble faz", "precio": 1290},
        {"nombre": "Cinta Embalaje", "precio": 1490},
        {"nombre": "Cinta Papel Grueso (masking)", "precio": 1390},
        {"nombre": "Cola fría 500 grs", "precio": 2990},
        {"nombre": "Silicona Líquida 250ml", "precio": 2190},
        {"nombre": "Pegamento en barra 115g", "precio": 2490},
        {"nombre": "Pegamento en barra 21g", "precio": 990},
        {"nombre": "Pegamento en barra 36g", "precio": 1490},

        {"nombre": "Goma Eva con Glitter (pliego chico)", "precio": 550},
        {"nombre": "Goma Eva en pliego grande Glitter", "precio": 1390},
        {"nombre": "Goma Eva en pliego grande normal", "precio": 990},
        {"nombre": "Goma Eva sin Glitter (chica)", "precio": 300},
        {"nombre": "Barras de Silicona (unidad)", "precio": 150},
        {"nombre": "Bastidor para pintar", "precio": 2490},
        {"nombre": "Palos de helado colores (pack)", "precio": 990},
        {"nombre": "Palos de helado grueso (pack)", "precio": 1190},
        {"nombre": "Palos de helado natural (pack)", "precio": 790},
        {"nombre": "Set Escarcha / Brillantina", "precio": 1290},
        {"nombre": "Set Brochas de espuma", "precio": 1990},
        {"nombre": "Set Pinceles económicos", "precio": 2490},
        {"nombre": "Set Limpiapipas / Limpieza", "precio": 1190},
        {"nombre": "Mezclador de pintura", "precio": 490},
        {"nombre": "Tijeras punta roma escolar", "precio": 890},
        {"nombre": "Tijeras grandes punta fina", "precio": 1890},
        {"nombre": "Tijeras grandes punta normal", "precio": 1690},

        {"nombre": "Carpeta Acolchada", "precio": 2190},
        {"nombre": "Carpeta Estuche con cierre", "precio": 1590},

        {"nombre": "Calculadora Normal de escritorio", "precio": 3990},
        {"nombre": "Calculadora Científica estándar", "precio": 9990},

        {"nombre": "Plumón Permanente (Negro/Azul/Rojo)", "precio": 790},
        {"nombre": "Plumón Pizarra", "precio": 890}
    ]

    print("⏳ Iniciando la carga del catálogo a la base de datos...")
    
    for item in inventario:
        if not Producto.objects.filter(nombre_producto=item["nombre"]).exists():
            Producto.objects.create(
                nombre_producto=item["nombre"],
                precio=item["precio"]
            )
            print(f"✅ Añadido: {item['nombre']} -> ${item['precio']}")
        else:
            print(f"⚠️ Ya existía: {item['nombre']}")

    print("🎉 ¡Todo el catálogo fue cargado con éxito en la base de datos!")

if __name__ == '__main__':
    cargar_productos()