"""Utilidades reutilizables para la Librería Chichi."""


def limpiar_rut(rut):
    """Quita puntos, guiones y espacios; deja el RUT en mayúsculas."""
    return (rut or '').replace('.', '').replace('-', '').replace(' ', '').upper()


def rut_es_valido(rut):
    """Valida un RUT chileno con el algoritmo módulo 11.

    Acepta formatos como '12345678-5', '12.345.678-5' o '123456785'.
    Devuelve True/False.
    """
    limpio = limpiar_rut(rut)
    if len(limpio) < 2:
        return False

    cuerpo, dv = limpio[:-1], limpio[-1]
    if not cuerpo.isdigit():
        return False
    if len(cuerpo) < 7 or len(cuerpo) > 8:
        return False

    suma, multiplo = 0, 2
    for c in reversed(cuerpo):
        suma += int(c) * multiplo
        multiplo = 2 if multiplo == 7 else multiplo + 1

    resto = suma % 11
    dv_esperado = 11 - resto
    if dv_esperado == 11:
        dv_esperado = '0'
    elif dv_esperado == 10:
        dv_esperado = 'K'
    else:
        dv_esperado = str(dv_esperado)

    return dv == dv_esperado


def formatear_rut(rut):
    """Devuelve el RUT como 'cuerpo-dv' (sin puntos). Si es inválido, lo
    retorna tal cual (limpio)."""
    limpio = limpiar_rut(rut)
    if len(limpio) < 2:
        return limpio
    return f"{limpio[:-1]}-{limpio[-1]}"


# ════════════════════════════════════════════════════════════════════════════
#  CORREOS DE SEGUIMIENTO DE PEDIDO
#  (usados desde views.py y api.py para avisar al cliente por email)
# ════════════════════════════════════════════════════════════════════════════
from django.core.mail import send_mail
from django.conf import settings


def _resumen_pedido_texto(pedido):
    """Devuelve (texto_detalle, total_int) de un pedido para el cuerpo del correo."""
    from .models import DetallePedido
    detalles = DetallePedido.objects.select_related('id_producto').filter(id_pedido=pedido)
    lineas = []
    total = 0
    for d in detalles:
        sub = float(d.precio_unitario) * d.cantidad
        total += sub
        lineas.append(f"  - {d.cantidad} x {d.id_producto.nombre_producto} (${int(d.precio_unitario)} c/u)")
    return "\n".join(lineas), int(total)


def enviar_correo_estado_pedido(pedido, nuevo_estado, motivo=None):
    """Avisa al cliente por correo según el nuevo estado del pedido.

    Estados manejados: 'confirmado', 'entregado', 'cancelado'.
    Devuelve True si había email y se intentó enviar; False si no.
    No lanza excepciones (fail_silently) para no romper el panel.
    """
    cliente = getattr(pedido, 'id_cliente', None)
    email = getattr(cliente, 'email', None)
    if not email:
        return False
    nombre = getattr(cliente, 'nombre', '') or 'cliente'
    resumen, total = _resumen_pedido_texto(pedido)

    if nuevo_estado == 'confirmado':
        asunto = f"Tu pedido #{pedido.id_pedido} fue confirmado ✅ — Librería Chichi"
        cuerpo = (
            f"Hola {nombre},\n\n"
            f"¡Buenas noticias! Confirmamos tu pedido #{pedido.id_pedido} y ya lo estamos preparando.\n\n"
            f"Detalle:\n{resumen}\n\nTotal: ${total}\n\n"
            f"Te avisaremos otra vez cuando esté listo para la entrega.\n\n"
            f"Un saludo,\nEquipo Librería Chichi"
        )
    elif nuevo_estado == 'entregado':
        asunto = f"Tu pedido #{pedido.id_pedido} fue entregado 📦 — Librería Chichi"
        cuerpo = (
            f"Hola {nombre},\n\n"
            f"Tu pedido #{pedido.id_pedido} fue marcado como ENTREGADO. ¡Esperamos que lo disfrutes!\n\n"
            f"Detalle:\n{resumen}\n\nTotal: ${total}\n\n"
            f"Gracias por comprar en Librería Chichi. Cualquier consulta, escríbenos.\n\n"
            f"Un saludo,\nEquipo Librería Chichi"
        )
    elif nuevo_estado == 'cancelado':
        motivo_txt = f"\nMotivo: {motivo}\n" if motivo else ""
        asunto = f"Tu pedido #{pedido.id_pedido} fue cancelado — Librería Chichi"
        cuerpo = (
            f"Hola {nombre},\n\n"
            f"Lamentamos informarte que tu pedido #{pedido.id_pedido} fue cancelado.{motivo_txt}\n"
            f"Detalle del pedido:\n{resumen}\n\nTotal: ${total}\n\n"
            f"REEMBOLSO: si ya habías pagado, te devolveremos el monto total (${total}). "
            f"Si pagaste por transferencia, el dinero se devolverá a tu cuenta bancaria. "
            f"Por favor responde a este correo confirmando tus datos bancarios "
            f"(banco, tipo y número de cuenta, RUT) para procesar la devolución a la brevedad.\n\n"
            f"Disculpa las molestias.\n\nEquipo Librería Chichi"
        )
    else:
        return False

    try:
        send_mail(
            subject=asunto,
            message=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,
        )
    except Exception as e:
        print(f"⚠️ No se pudo enviar correo de estado ({nuevo_estado}) del pedido #{getattr(pedido,'id_pedido','?')}: {e}")
    return True


def enviar_correo_transferencia_rechazada(transferencia, motivo):
    """Avisa al cliente que su transferencia no pudo validarse."""
    pedido = transferencia.id_pedido
    cliente = getattr(pedido, 'id_cliente', None)
    email = getattr(cliente, 'email', None) or transferencia.email_contacto
    if not email:
        return False
    nombre = getattr(cliente, 'nombre', '') or 'cliente'
    try:
        send_mail(
            subject=f"Problema con la transferencia de tu pedido #{pedido.id_pedido} — Librería Chichi",
            message=(
                f"Hola {nombre},\n\n"
                f"Revisamos la transferencia informada para tu pedido #{pedido.id_pedido} y no pudimos validarla.\n\n"
                f"Motivo: {motivo}\n\n"
                f"Tu pedido quedará pendiente. Puedes volver a informar la transferencia con los datos correctos, "
                f"o escribirnos respondiendo a este correo para ayudarte.\n\n"
                f"Un saludo,\nEquipo Librería Chichi"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,
        )
    except Exception as e:
        print(f"⚠️ No se pudo enviar correo de transferencia rechazada: {e}")
    return True
