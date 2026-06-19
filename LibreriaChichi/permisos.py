"""
═══════════════════════════════════════════════════════════════════════════
  SISTEMA DE ROLES Y PERMISOS — Librería Chichi
═══════════════════════════════════════════════════════════════════════════

Este módulo centraliza TODO lo relacionado con "quién puede hacer qué".
Antes, cada vista repetía chequeos sueltos como:

    if not request.user.is_superuser: ...
    if _es_bodeguero(request.user): ...

Eso es frágil y difícil de mantener. Aquí definimos los roles con
*Grupos de Django* y exponemos funciones claras (es_administrador,
puede_usar_pos, etc.) y decoradores (@requiere) para usar en las vistas.

ROLES DE LA LIBRERÍA
────────────────────
  • SUPER ADMIN (dueño/gerente)  → is_superuser=True. Control total.
  • ADMINISTRADOR               → Grupo "Administrador".
  • CAJERO / VENDEDOR           → Grupo "Cajero".
  • BODEGUERO                   → Grupo "Bodeguero".

MATRIZ DE PERMISOS
──────────────────
  Accion                          Super  Admin  Cajero  Bodeguero
  Ingresar producto nuevo          SI     SI      NO      SI
  Editar producto / precio         SI     SI      NO      NO
  Reabastecer stock                SI     SI      NO      NO
  Eliminar producto                SI     NO      NO      NO
  Ver precios y stock              SI     SI      SI      NO
  Punto de Venta (POS)             SI     SI      SI      NO
  Gestionar pedidos / envios       SI     SI      NO      NO
  Reportes de ventas               SI     SI      NO      NO
  Generar boleta                   SI     SI      SI      NO
  Validar transferencias           SI     SI      SI      NO
  Crear / eliminar administradores SI     NO      NO      NO

Los Grupos y sus permisos se crean automáticamente al ejecutar
`python manage.py migrate` (ver apps.py → señal post_migrate) y también
con `python manage.py setup_roles`.
"""

from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


# ── Nombres de los grupos (única fuente de verdad) ───────────────────────────
GRUPO_ADMIN = 'Administrador'
GRUPO_CAJERO = 'Cajero'
GRUPO_BODEGUERO = 'Bodeguero'

# Permiso personalizado (definido en models.Transferencia.Meta.permissions)
PERM_VALIDAR_TRANSFERENCIA = 'LibreriaChichi.validar_transferencia'
# Permiso usado para distinguir al administrador del bodeguero (compatibilidad)
PERM_CAMBIAR_PRODUCTO = 'LibreriaChichi.change_producto'


# ════════════════════════════════════════════════════════════════════════════
#  1. DETECCIÓN DE ROL
#     (combina Grupos nuevos + lógica antigua, para no romper usuarios viejos)
# ════════════════════════════════════════════════════════════════════════════
def _autenticado(user):
    return bool(user and user.is_authenticated)


def _en_grupo(user, nombre):
    return _autenticado(user) and user.groups.filter(name=nombre).exists()


def es_superadmin(user):
    """Dueño/gerente: acceso total."""
    return _autenticado(user) and user.is_superuser


def es_administrador(user):
    """Administrador de catálogo, pedidos y reportes (no es superusuario).

    Reconoce el Grupo nuevo y, por compatibilidad, a los admins antiguos que
    fueron creados con el permiso change_producto asignado directamente.
    """
    if not _autenticado(user) or user.is_superuser:
        return False
    if _en_grupo(user, GRUPO_ADMIN):
        return True
    # Compatibilidad con usuarios creados antes de los Grupos:
    return (user.is_staff
            and user.has_perm(PERM_CAMBIAR_PRODUCTO)
            and not _en_grupo(user, GRUPO_CAJERO)
            and not _en_grupo(user, GRUPO_BODEGUERO))


def es_cajero(user):
    """Cajero / vendedor de mostrador."""
    return _en_grupo(user, GRUPO_CAJERO)


def es_bodeguero(user):
    """Bodeguero: solo ingresa productos nuevos (sin precio ni stock)."""
    if not _autenticado(user) or user.is_superuser:
        return False
    if _en_grupo(user, GRUPO_BODEGUERO):
        return True
    # Compatibilidad con bodegueros antiguos (staff sin permiso de cambio y
    # que no son cajeros).
    return (user.is_staff
            and not user.has_perm(PERM_CAMBIAR_PRODUCTO)
            and not _en_grupo(user, GRUPO_CAJERO)
            and not _en_grupo(user, GRUPO_ADMIN))


def rol_legible(user):
    """Devuelve el nombre del rol en español, para mostrar en pantalla."""
    if es_superadmin(user):
        return 'Super Admin'
    if es_administrador(user):
        return 'Administrador'
    if es_cajero(user):
        return 'Cajero'
    if es_bodeguero(user):
        return 'Bodeguero'
    return 'Cliente'


def rol_key(user):
    """Devuelve el código interno del rol (el mismo que usan los formularios:
    'super_admin', 'admin_completo', 'cajero', 'bodeguero')."""
    if es_superadmin(user):
        return 'super_admin'
    if es_administrador(user):
        return 'admin_completo'
    if es_cajero(user):
        return 'cajero'
    if es_bodeguero(user):
        return 'bodeguero'
    return 'cliente'


# ════════════════════════════════════════════════════════════════════════════
#  2. CAPACIDADES  (lo que cada vista debe preguntar)
# ════════════════════════════════════════════════════════════════════════════
def es_backoffice(user):
    """Cualquier rol interno (entra al panel de gestión)."""
    return _autenticado(user) and (user.is_staff or user.is_superuser)


def puede_ingresar_productos(user):
    return es_superadmin(user) or es_administrador(user) or es_bodeguero(user)


def puede_gestionar_inventario(user):
    """Editar productos, cambiar precios y reabastecer stock."""
    return es_superadmin(user) or es_administrador(user)


def puede_eliminar_producto(user):
    return es_superadmin(user)


def puede_ver_precio_stock(user):
    """El bodeguero NO ve precios ni stock; el resto sí."""
    return es_backoffice(user) and not es_bodeguero(user)


def puede_usar_pos(user):
    return es_superadmin(user) or es_administrador(user) or es_cajero(user)


def puede_gestionar_pedidos(user):
    return es_superadmin(user) or es_administrador(user)


def puede_ver_reportes(user):
    return es_superadmin(user) or es_administrador(user)


def puede_generar_boleta(user):
    return puede_usar_pos(user) or puede_gestionar_pedidos(user)


def puede_validar_transferencias(user):
    return _autenticado(user) and (
        es_superadmin(user) or user.has_perm(PERM_VALIDAR_TRANSFERENCIA)
    )


def puede_gestionar_admins(user):
    return es_superadmin(user)


def permisos_para_template(user):
    """Diccionario listo para enviar al contexto de las plantillas."""
    return {
        'rol': rol_legible(user),
        'es_super': es_superadmin(user),
        'es_admin': es_administrador(user),
        'es_cajero': es_cajero(user),
        'es_bodeguero': es_bodeguero(user),
        'puede_gestionar_productos': puede_ingresar_productos(user),
        'puede_gestionar_inventario': puede_gestionar_inventario(user),
        'puede_gestionar_admins': puede_gestionar_admins(user),
        'puede_cambiar_precio': puede_gestionar_inventario(user),
        'puede_ver_precio_stock': puede_ver_precio_stock(user),
        'puede_editar': puede_gestionar_inventario(user),
        'puede_eliminar': puede_eliminar_producto(user),
        'puede_usar_pos': puede_usar_pos(user),
        'puede_gestionar_pedidos': puede_gestionar_pedidos(user),
        'puede_ver_reportes': puede_ver_reportes(user),
        'puede_validar_transferencias': puede_validar_transferencias(user),
    }


# ════════════════════════════════════════════════════════════════════════════
#  3. DECORADOR PARA VISTAS
# ════════════════════════════════════════════════════════════════════════════
def requiere(test, mensaje="No tienes permiso para acceder a esta sección.",
            destino='inicio'):
    """Decorador genérico: protege una vista con una función de capacidad.

    Uso:
        @requiere(puede_usar_pos, "No tienes acceso al punto de venta.",
                  destino='panel_admin')
        def panel_pos(request): ...
    """
    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not _autenticado(request.user):
                messages.error(request, "Debes iniciar sesión.")
                return redirect('login_admin')
            if not test(request.user):
                messages.error(request, mensaje)
                return redirect(destino)
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador


# ════════════════════════════════════════════════════════════════════════════
#  4. CREACIÓN / ACTUALIZACIÓN DE GRUPOS Y PERMISOS
#     (idempotente — se puede ejecutar mil veces sin problema)
# ════════════════════════════════════════════════════════════════════════════
# Qué permisos del modelo recibe cada grupo. Formato: 'app.codename'.
PERMISOS_POR_GRUPO = {
    GRUPO_ADMIN: [
        'LibreriaChichi.add_producto', 'LibreriaChichi.change_producto',
        'LibreriaChichi.view_producto',
        'LibreriaChichi.add_stock', 'LibreriaChichi.change_stock',
        'LibreriaChichi.view_stock',
        'LibreriaChichi.view_pedido', 'LibreriaChichi.change_pedido',
        'LibreriaChichi.view_pago', 'LibreriaChichi.change_pago',
        'LibreriaChichi.add_pago',
        'LibreriaChichi.view_transferencia',
        'LibreriaChichi.change_transferencia',
        'LibreriaChichi.add_transferencia',
        'LibreriaChichi.validar_transferencia',
    ],
    GRUPO_CAJERO: [
        'LibreriaChichi.view_producto',
        'LibreriaChichi.view_stock',
        'LibreriaChichi.add_pedido', 'LibreriaChichi.view_pedido',
        'LibreriaChichi.add_pago', 'LibreriaChichi.view_pago',
        'LibreriaChichi.view_transferencia',
        'LibreriaChichi.add_transferencia',
        'LibreriaChichi.change_transferencia',
        'LibreriaChichi.validar_transferencia',
    ],
    GRUPO_BODEGUERO: [
        'LibreriaChichi.add_producto',
        'LibreriaChichi.view_producto',
    ],
}


def configurar_roles(verbose=False):
    """Crea (o actualiza) los Grupos con sus permisos y migra usuarios
    antiguos a los Grupos según los flags/permisos que ya tenían.

    Es seguro llamarla en cualquier momento. La invoca automáticamente la
    señal post_migrate (apps.py) y el comando `manage.py setup_roles`.
    """
    # Imports locales: este módulo se importa al cargar la app y no debe
    # tocar la base de datos a nivel de módulo.
    from django.contrib.auth.models import Group, Permission, User

    def _buscar_permiso(etiqueta):
        app_label, codename = etiqueta.split('.', 1)
        try:
            return Permission.objects.get(
                content_type__app_label=app_label, codename=codename
            )
        except Permission.DoesNotExist:
            return None

    # 1) Crear grupos y asignar permisos
    for nombre_grupo, etiquetas in PERMISOS_POR_GRUPO.items():
        grupo, _ = Group.objects.get_or_create(name=nombre_grupo)
        permisos = [p for p in (_buscar_permiso(e) for e in etiquetas) if p]
        grupo.permissions.set(permisos)
        if verbose:
            print(f"  • Grupo '{nombre_grupo}': {len(permisos)} permisos")

    # 2) Backfill: ubicar a usuarios existentes en el grupo correcto
    grupo_admin = Group.objects.get(name=GRUPO_ADMIN)
    grupo_bodeguero = Group.objects.get(name=GRUPO_BODEGUERO)

    movidos = 0
    for u in User.objects.filter(is_staff=True, is_superuser=False):
        ya_tiene_grupo = u.groups.filter(
            name__in=[GRUPO_ADMIN, GRUPO_CAJERO, GRUPO_BODEGUERO]
        ).exists()
        if ya_tiene_grupo:
            continue
        tiene_cambio = u.user_permissions.filter(
            codename='change_producto'
        ).exists()
        if tiene_cambio:
            u.groups.add(grupo_admin)
            movidos += 1
        elif u.user_permissions.filter(codename='add_producto').exists():
            u.groups.add(grupo_bodeguero)
            movidos += 1
    if verbose and movidos:
        print(f"  • {movidos} usuario(s) antiguo(s) asignado(s) a un grupo")

    return True
