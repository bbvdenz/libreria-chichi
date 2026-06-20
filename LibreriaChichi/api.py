"""
═══════════════════════════════════════════════════════════════════════════
  API DE VALIDACIÓN DE TRANSFERENCIAS — Librería Chichi
═══════════════════════════════════════════════════════════════════════════

API JSON (sin librerías externas, solo Django) para informar y validar
transferencias bancarias.

FLUJO
─────
  1. El cliente paga con transferencia y reporta el comprobante:
         POST /api/v1/transferencias/registrar/
     La API valida automáticamente: RUT correcto, monto > 0, comprobante no
     duplicado y si el monto COINCIDE con el total del pedido.
     La transferencia queda en estado "pendiente".

  2. Un administrador o cajero revisa y aprueba/rechaza:
         POST /api/v1/transferencias/<id>/validar/
     Al aprobar, el pedido pasa a "confirmado" y se registra el Pago.

AUTENTICACIÓN
─────────────
  • Por sesión: estar logueado como staff con permiso de validar.
  • Por clave de API: enviar la cabecera  X-API-Key: <clave>
    (las claves se administran en el panel de Django → "Claves API").

Todas las respuestas son JSON con la forma:
    { "ok": true|false, ... }
"""

import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import ClaveAPI, DetallePedido, Pago, Pedido, Transferencia
from .permisos import puede_validar_transferencias
from .utils import formatear_rut, rut_es_valido
from .utils import enviar_correo_estado_pedido, enviar_correo_transferencia_rechazada


# ════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════════════════════
def _json(data, status=200):
    return JsonResponse(data, status=status, json_dumps_params={'ensure_ascii': False})


def _error(mensaje, status=400, **extra):
    cuerpo = {'ok': False, 'error': mensaje}
    cuerpo.update(extra)
    return _json(cuerpo, status=status)


def _leer_json(request):
    """Lee el cuerpo JSON; si viene como formulario, usa request.POST."""
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body or b'{}')
        except (ValueError, TypeError):
            return None
    return request.POST.dict() if request.method == 'POST' else {}


def _clave_api_valida(request):
    """¿La cabecera X-API-Key corresponde a una clave activa?"""
    clave = request.headers.get('X-API-Key', '').strip()
    if not clave:
        return False
    return ClaveAPI.objects.filter(clave=clave, activa=True).exists()


def total_pedido(pedido):
    """Suma de todos los detalles del pedido (precio_unitario * cantidad)."""
    total = Decimal('0')
    for d in DetallePedido.objects.filter(id_pedido=pedido):
        total += Decimal(str(d.precio_unitario)) * d.cantidad
    return total


# ── Decoradores de autenticación ─────────────────────────────────────────────
def api(metodos):
    """Marca una función como endpoint de API: exime CSRF, limita el método
    HTTP y atrapa errores inesperados devolviéndolos como JSON."""
    def decorador(vista):
        @csrf_exempt
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if request.method not in metodos:
                return _error(f"Método no permitido. Usa: {', '.join(metodos)}.",
                              status=405)
            try:
                return vista(request, *args, **kwargs)
            except Http404:
                return _error("Recurso no encontrado.", status=404)
            except Exception as e:  # red de seguridad
                return _error(f"Error interno: {e}", status=500)
        return envoltura
    return decorador


def requiere_acceso(vista):
    """Permite el acceso si hay clave de API válida O sesión de staff."""
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if _clave_api_valida(request):
            return vista(request, *args, **kwargs)
        if request.user.is_authenticated and request.user.is_staff:
            return vista(request, *args, **kwargs)
        return _error("No autorizado. Inicia sesión o envía una X-API-Key válida.",
                      status=401)
    return envoltura


def requiere_validador(vista):
    """Acción privilegiada (validar): clave de API válida O usuario con
    permiso de validar transferencias."""
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if _clave_api_valida(request):
            return vista(request, *args, **kwargs)
        if puede_validar_transferencias(request.user):
            return vista(request, *args, **kwargs)
        return _error("No tienes permiso para validar transferencias.", status=403)
    return envoltura


# ════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════
@api(['GET'])
def ping(request):
    """Chequeo de salud de la API."""
    return _json({'ok': True, 'servicio': 'API Transferencias Librería Chichi',
                  'hora': timezone.now().isoformat()})


@api(['POST'])
def registrar_transferencia(request):
    """Registra una transferencia informada por el cliente y la valida
    automáticamente (queda 'pendiente' de aprobación manual).

    Campos (JSON o formulario):
        pedido_id            (obligatorio)
        banco                (obligatorio)
        numero_operacion     (obligatorio)
        rut_pagador          (obligatorio, RUT chileno)
        monto                (obligatorio, > 0)
        fecha_transferencia  (obligatorio, formato AAAA-MM-DD)
        email_contacto       (opcional)
    """
    datos = _leer_json(request)
    if datos is None:
        return _error("El cuerpo no es JSON válido.")

    requeridos = ['pedido_id', 'banco', 'numero_operacion',
                  'rut_pagador', 'monto', 'fecha_transferencia']
    faltan = [c for c in requeridos if not str(datos.get(c, '')).strip()]
    if faltan:
        return _error(f"Faltan campos obligatorios: {', '.join(faltan)}.")

    # ── Pedido ──
    try:
        pedido = Pedido.objects.get(pk=int(datos['pedido_id']))
    except (Pedido.DoesNotExist, ValueError, TypeError):
        return _error("El pedido indicado no existe.", status=404)

    # ── RUT ──
    rut = formatear_rut(datos['rut_pagador'])
    if not rut_es_valido(rut):
        return _error("El RUT del pagador no es válido.")

    # ── Monto ──
    try:
        monto = Decimal(str(datos['monto']))
    except (InvalidOperation, ValueError, TypeError):
        return _error("El monto no es un número válido.")
    if monto <= 0:
        return _error("El monto debe ser mayor que cero.")
    # El campo admite hasta 10 dígitos (máx 99.999.999,99). Evita un error de BD.
    if monto >= Decimal('100000000'):
        return _error("El monto es demasiado grande.")

    # ── Fecha ──
    try:
        fecha = datetime.strptime(str(datos['fecha_transferencia'])[:10], '%Y-%m-%d').date()
    except ValueError:
        return _error("La fecha debe tener el formato AAAA-MM-DD.")

    # Recortamos a la longitud máxima de cada campo para no romper la BD.
    banco = str(datos['banco']).strip()[:80]
    numero_operacion = str(datos['numero_operacion']).strip()[:60]

    # ── No duplicar comprobante ──
    if Transferencia.objects.filter(banco=banco, numero_operacion=numero_operacion).exists():
        return _error("Ese N° de operación ya fue informado para ese banco.",
                      status=409)

    # ── El pedido no debe tener ya una transferencia validada ──
    if pedido.transferencias.filter(estado=Transferencia.ESTADO_VALIDADA).exists():
        return _error("Este pedido ya tiene una transferencia validada.",
                      status=409)

    # ── Validación automática del monto ──
    esperado = total_pedido(pedido)
    coincide = abs(monto - esperado) <= Decimal('1')  # tolerancia $1 por redondeo

    transferencia = Transferencia.objects.create(
        id_pedido=pedido,
        banco=banco,
        numero_operacion=numero_operacion,
        rut_pagador=rut,
        monto=monto,
        fecha_transferencia=fecha,
        email_contacto=((datos.get('email_contacto') or '').strip()[:254] or None),
        coincide_monto=coincide,
        estado=Transferencia.ESTADO_PENDIENTE,
    )

    return _json({
        'ok': True,
        'mensaje': 'Transferencia registrada. Queda pendiente de validación.',
        'monto_esperado': float(esperado),
        'coincide_monto': coincide,
        'transferencia': transferencia.como_dict(),
    }, status=201)


@api(['GET'])
@requiere_acceso
def listar_transferencias(request):
    """Lista transferencias. Filtros opcionales: ?estado= y ?pedido=."""
    qs = Transferencia.objects.all()
    estado = request.GET.get('estado', '').strip()
    if estado:
        qs = qs.filter(estado=estado)
    pedido = request.GET.get('pedido', '').strip()
    if pedido.isdigit():
        qs = qs.filter(id_pedido_id=int(pedido))

    return _json({
        'ok': True,
        'cantidad': qs.count(),
        'transferencias': [t.como_dict() for t in qs[:200]],
    })


@api(['GET'])
@requiere_acceso
def detalle_transferencia(request, transferencia_id):
    """Detalle de una transferencia, incluyendo el total esperado del pedido."""
    t = get_object_or_404(Transferencia, pk=transferencia_id)
    datos = t.como_dict()
    datos['monto_esperado'] = float(total_pedido(t.id_pedido))
    return _json({'ok': True, 'transferencia': datos})


@api(['POST'])
@requiere_validador
def validar_transferencia(request, transferencia_id):
    """Aprueba o rechaza una transferencia.

    Campos:
        decision : 'aprobar' | 'rechazar'   (obligatorio)
        motivo   : texto (obligatorio si se rechaza)

    Al APROBAR: el pedido pasa a 'confirmado' y se registra el Pago.
    """
    t = get_object_or_404(Transferencia, pk=transferencia_id)
    if t.estado != Transferencia.ESTADO_PENDIENTE:
        return _error(f"La transferencia ya fue {t.estado}. No se puede volver a procesar.",
                      status=409)

    datos = _leer_json(request) or {}
    decision = str(datos.get('decision', '')).strip().lower()
    usuario = request.user if request.user.is_authenticated else None

    if decision == 'aprobar':
        # No tiene sentido aprobar el pago de un pedido cancelado.
        if t.id_pedido.estado_pedido == 'cancelado':
            return _error("No se puede aprobar: el pedido está cancelado.", status=409)
        # Registrar el pago asociado
        pago = Pago.objects.create(
            monto=t.monto,
            metodo_pago='Transferencia',
            estado_pago='Aprobado',
            fecha_pago=timezone.now().date(),
        )
        t.id_pago = pago
        t.estado = Transferencia.ESTADO_VALIDADA
        t.validado_por = usuario
        t.validado_en = timezone.now()
        t.motivo_rechazo = None
        t.save()

        # Confirmar el pedido si estaba pendiente
        pedido = t.id_pedido
        if pedido.estado_pedido in ('pendiente', ''):
            pedido.estado_pedido = 'confirmado'
            pedido.save()
            # Avisar al cliente que su pago fue validado y el pedido confirmado
            enviar_correo_estado_pedido(pedido, 'confirmado')

        return _json({
            'ok': True,
            'mensaje': f'Transferencia aprobada. Pedido #{pedido.id_pedido} confirmado.',
            'transferencia': t.como_dict(),
        })

    elif decision == 'rechazar':
        motivo = str(datos.get('motivo', '')).strip()
        if not motivo:
            return _error("Debes indicar el 'motivo' del rechazo.")
        t.estado = Transferencia.ESTADO_RECHAZADA
        t.motivo_rechazo = motivo
        t.validado_por = usuario
        t.validado_en = timezone.now()
        t.save()
        # Avisar al cliente del rechazo y el motivo
        enviar_correo_transferencia_rechazada(t, motivo)
        return _json({
            'ok': True,
            'mensaje': 'Transferencia rechazada.',
            'transferencia': t.como_dict(),
        })

    return _error("La 'decision' debe ser 'aprobar' o 'rechazar'.")
