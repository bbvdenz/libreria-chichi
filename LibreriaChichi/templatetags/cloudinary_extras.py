"""
Filtros de plantilla para optimizar imágenes de Cloudinary.

Cloudinary permite pedir versiones optimizadas de una imagen agregando
"transformaciones" en la URL, justo después de '/upload/'. Por ejemplo:

  .../upload/v123/chichi/foto.png
  .../upload/f_auto,q_auto,w_400/v123/chichi/foto.png   ← optimizada

  f_auto  → entrega el mejor formato (WebP/AVIF) según el navegador
  q_auto  → comprime con la mejor calidad/peso automáticamente
  w_400   → ancho máximo 400px (no necesitamos más para una tarjeta)

Resultado: imágenes ~70% más livianas y carga mucho más rápida,
sin tener que volver a subir nada.
"""

from django import template

register = template.Library()


@register.filter
def optimizar(url, opciones="f_auto,q_auto,w_400"):
    """Inserta transformaciones de Cloudinary en la URL de la imagen.

    Si la URL no es de Cloudinary (o está vacía), la devuelve tal cual.
    """
    if not url or "res.cloudinary.com" not in url or "/upload/" not in url:
        return url
    # Evita duplicar si ya tiene transformaciones aplicadas
    partes = url.split("/upload/", 1)
    if partes[1].startswith(opciones):
        return url
    return f"{partes[0]}/upload/{opciones}/{partes[1]}"
