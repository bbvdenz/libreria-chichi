from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings
from .models import Producto, Cliente, Pedido, DetallePedido, Stock, Pago
from .models import Transferencia
from .forms import RegistroClienteForm
from . import permisos
from .utils import enviar_correo_estado_pedido
from decimal import Decimal, InvalidOperation
from django.db.models import Q, ProtectedError, RestrictedError
from django.db import IntegrityError, transaction
import re
import unicodedata


# ── Generación automática de SKU ────────────────────────────────────────────
def _sin_acentos(texto):
    """Devuelve el texto en minúsculas y sin tildes/acentos.
    Sirve para buscar 'lapiz' y encontrar 'Lápiz'."""
    t = unicodedata.normalize('NFD', (texto or ''))
    return ''.join(c for c in t if unicodedata.category(c) != 'Mn').lower()


PREFIJOS_SKU = {
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


def _prefijo_sku(categoria):
    cat = (categoria or '').strip().upper()
    if cat in PREFIJOS_SKU:
        return PREFIJOS_SKU[cat]
    letras = ''.join(c for c in cat if c.isalpha())
    return (letras[:3] or 'GEN').upper()


def _siguiente_sku(categoria):
    """Devuelve el próximo SKU correlativo para la categoría, ej: 'PIN-001'.
    Toma el mayor número ya usado con ese prefijo y le suma 1 (a prueba de choques)."""
    prefijo = _prefijo_sku(categoria)
    maximo = 0
    existentes = (
        Producto.objects.filter(sku__startswith=prefijo + '-')
        .values_list('sku', flat=True)
    )
    for s in existentes:
        m = re.search(r'-(\d+)', s or '')
        if m:
            maximo = max(maximo, int(m.group(1)))
    n = maximo + 1
    sku = f"{prefijo}-{n:03d}"
    # Seguridad extra ante cualquier choque
    while Producto.objects.filter(sku=sku).exists():
        n += 1
        sku = f"{prefijo}-{n:03d}"
    return sku



# ── 0. PÁGINA BASE ──────────────────────────────────────────────────────────
def inicio_base(request):
    from .models import Stock
    productos_destacados = Producto.objects.filter(activo=True)[:12]
    destacados = []
    for p in productos_destacados:
        try:
            stock_obj = Stock.objects.get(id_producto=p)
            stock = stock_obj.cantidad_disponible
        except:
            stock = 0
        destacados.append({
            'id': p.id_producto,
            'nombre': p.nombre_producto,
            'categoria': p.categoria,
            'precio': int(p.precio),
            'stock': stock,
            'imagen': p.imagen.url if p.imagen else None,
            'emoji': '📚',
        })
    return render(request, 'base.html', {'destacados': destacados})


# ── 1. REGISTRO ──────────────────────────────────────────────────────────────
def registro_usuario(request):
    if request.method == 'POST':
        form = RegistroClienteForm(request.POST)
        if form.is_valid():
            rut_usuario = form.cleaned_data['rut']
            email_usuario = form.cleaned_data.get('email') or ''
            nombre_completo = f"{form.cleaned_data['nombre']} {form.cleaned_data['apellido']}"
            direccion_unificada = (
                f"{form.cleaned_data['direccion_calle']}, "
                f"{form.cleaned_data['comuna']}, "
                f"{form.cleaned_data['region']}"
            )
            # Defensa ante doble envío / carrera: si el RUT ya tiene cuenta,
            # no intentamos crearla otra vez (evita el error de "no se pudo crear").
            if User.objects.filter(username=rut_usuario).exists():
                messages.info(request, "Ya existe una cuenta con ese RUT. Inicia sesión.")
                return redirect('login')
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=rut_usuario,
                        email=email_usuario,
                        password=form.cleaned_data['password'],
                        first_name=form.cleaned_data['nombre'],
                        last_name=form.cleaned_data['apellido'],
                    )
                    Cliente.objects.create(
                        usuario=user,
                        rut=rut_usuario,
                        nombre=nombre_completo,
                        email=email_usuario,
                        telefono=form.cleaned_data['telefono'],
                        direccion_facturacion=direccion_unificada,
                    )
            except IntegrityError:
                # Dos envíos casi simultáneos: otro ya creó la cuenta.
                messages.info(request, "Ya existe una cuenta con ese RUT. Inicia sesión.")
                return redirect('login')
            login(request, user)
            messages.success(request, f"¡Bienvenido {user.first_name}! Tu cuenta fue creada exitosamente.")

            # ── Correo de bienvenida ──
            # fail_silently=True: si el correo falla, NO rompemos el registro.
            if email_usuario:
                try:
                    send_mail(
                        subject='¡Bienvenido a Librería Chichi! 📚',
                        message=(
                            f"Hola {user.first_name},\n\n"
                            f"¡Gracias por registrarte en Librería Chichi!\n"
                            f"Tu cuenta fue creada correctamente con el RUT {rut_usuario}.\n\n"
                            f"Ya puedes explorar nuestro catálogo y realizar tus compras.\n\n"
                            f"Un saludo,\nEquipo Librería Chichi"
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email_usuario],
                        fail_silently=True,
                    )
                except Exception as e:
                    print(f"⚠️ No se pudo enviar correo de bienvenida: {e}")

            if request.session.get('carrito'):
                return redirect('procesar_pago')
            return redirect('inicio')
    else:
        form = RegistroClienteForm()
    return render(request, 'registro.html', {'form': form})


# ── 2. LOGIN ─────────────────────────────────────────────────────────────────
def iniciar_sesion(request):
    if request.user.is_authenticated:
        return redirect('inicio')

    if request.method == 'POST':
        rut = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, username=rut, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"¡Hola de nuevo, {user.first_name or user.username}!")
            if request.session.get('carrito'):
                return redirect('procesar_pago')
            return redirect('inicio')
        else:
            messages.error(request, "RUT o contraseña incorrectos. Recuerda el formato: 12345678-9")

    return render(request, 'login.html', {})


def cerrar_sesion(request):
    logout(request)
    messages.info(request, "Has cerrado sesión exitosamente.")
    return redirect('inicio')


# ── 3. RECUPERAR CONTRASEÑA ──────────────────────────────────────────────────
def recuperar_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        users = User.objects.filter(email=email)
        if users.exists():
            for user in users:
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                reset_url = request.build_absolute_uri(
                    f"/recuperar-password/confirmar/{uid}/{token}/"
                )
                send_mail(
                    subject='Recuperar contraseña — Librería Chichi',
                    message=(
                        f"Hola {user.first_name or user.username},\n\n"
                        f"Haz click aquí para restablecer tu contraseña:\n{reset_url}\n\n"
                        f"Si no solicitaste esto, ignora este correo."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    # fail_silently=False mientras configuras: si el SMTP falla,
                    # verás el error en los logs de Azure en vez de un "éxito"
                    # silencioso. Cuando ya funcione, puedes ponerlo en True.
                    fail_silently=False,
                )
        messages.success(request, "Si el correo existe en nuestro sistema, recibirás el enlace.")
        return redirect('login')
    return render(request, 'recuperar_password.html', {})


def confirmar_nueva_password(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except Exception:
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        messages.error(request, "El enlace no es válido o ya expiró.")
        return redirect('login')

    if request.method == 'POST':
        nueva = request.POST.get('nueva_password', '')
        confirmar = request.POST.get('confirmar_password', '')
        if len(nueva) < 8:
            messages.error(request, "La contraseña debe tener al menos 8 caracteres.")
        elif nueva != confirmar:
            messages.error(request, "Las contraseñas no coinciden.")
        else:
            user.set_password(nueva)
            user.save()
            messages.success(request, "¡Contraseña actualizada! Ya puedes iniciar sesión.")
            return redirect('login')
    return render(request, 'nueva_password.html', {'uidb64': uidb64, 'token': token})


# ── 4. CATÁLOGO ──────────────────────────────────────────────────────────────
def catalogo_publico(request):
    categoria_filtro = request.GET.get('cat', '').strip().upper()
    busqueda = request.GET.get('q', '').strip()

    productos = Producto.objects.filter(activo=True)

    # ── Buscador (lupa) para el cliente: solo por NOMBRE (el SKU es interno) ──
    if busqueda:
        productos = productos.filter(nombre_producto__icontains=busqueda)

    productos_por_seccion = {}

    for prod in productos:
        try:
            stock_obj = Stock.objects.get(id_producto=prod)
            prod.stock_disponible = stock_obj.cantidad_disponible
        except Stock.DoesNotExist:
            prod.stock_disponible = None

        cat = prod.categoria
        if cat not in productos_por_seccion:
            productos_por_seccion[cat] = []
        productos_por_seccion[cat].append(prod)

    return render(request, 'catalogo.html', {
        'productos_por_seccion': productos_por_seccion,
        'categoria_filtro': categoria_filtro,
        'busqueda': busqueda,
    })


# ── 5. CARRITO ───────────────────────────────────────────────────────────────
def agregar_al_carrito(request, producto_id):
    if request.method == 'POST':
        cantidad = int(request.POST.get('cantidad', 1))
        accion = request.POST.get('accion', 'carrito')
        producto = get_object_or_404(Producto, pk=producto_id)

        try:
            stock_obj = Stock.objects.get(id_producto=producto)
            stock_disponible = stock_obj.cantidad_disponible
        except Stock.DoesNotExist:
            messages.error(request, f"⚠️ {producto.nombre_producto} no tiene stock registrado.")
            return redirect(request.META.get('HTTP_REFERER', '/'))

        id_str = str(producto_id)

        # ── Compra rápida ("Comprar Ahora"): NO toca el carrito permanente.
        # Se guarda aparte y se compra solo ese producto. Si el cliente vuelve
        # atrás sin pagar, el carrito queda intacto y no se acumula nada.
        if accion == 'comprar':
            if cantidad > stock_disponible:
                messages.error(request, f"❌ Solo quedan {stock_disponible} unidades disponibles.")
                return redirect(request.META.get('HTTP_REFERER', '/'))
            request.session['comprar_ahora'] = {id_str: cantidad}
            request.session.modified = True
            return redirect('procesar_pago')

        # ── Agregar al carrito normal ──
        carrito = request.session.get('carrito', {})
        nueva_cantidad = carrito.get(id_str, 0) + cantidad

        if nueva_cantidad > stock_disponible:
            messages.error(request, f"❌ Solo quedan {stock_disponible} unidades disponibles.")
            return redirect(request.META.get('HTTP_REFERER', '/'))

        carrito[id_str] = nueva_cantidad
        request.session['carrito'] = carrito
        # Si había una compra rápida pendiente, se descarta (ahora usa el carrito).
        request.session['comprar_ahora'] = {}
        request.session.modified = True

        messages.success(request, f"✅ {cantidad} x {producto.nombre_producto} agregado al carrito.")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    return redirect(request.META.get('HTTP_REFERER', '/'))


def ver_carrito(request):
    # El cliente usa el carrito normal: descartar cualquier compra rápida pendiente.
    if request.session.get('comprar_ahora'):
        request.session['comprar_ahora'] = {}
        request.session.modified = True
    carrito = request.session.get('carrito', {})
    productos_carrito = []
    total = 0
    for prod_id, cantidad in carrito.items():
        producto = get_object_or_404(Producto, pk=prod_id)
        subtotal = producto.precio * cantidad
        total += subtotal
        try:
            stock_obj = Stock.objects.get(id_producto=producto)
            stock_disponible = stock_obj.cantidad_disponible
        except Stock.DoesNotExist:
            stock_disponible = 0
        productos_carrito.append({
            'producto': producto,
            'cantidad': cantidad,
            'subtotal': subtotal,
            'stock_disponible': stock_disponible,
        })
    return render(request, 'carrito.html', {'productos_carrito': productos_carrito, 'total': total})


def modificar_carrito(request, producto_id, accion):
    carrito = request.session.get('carrito', {})
    id_str = str(producto_id)
    if id_str in carrito:
        if accion == 'sumar':
            producto = get_object_or_404(Producto, pk=producto_id)
            try:
                stock_obj = Stock.objects.get(id_producto=producto)
                if carrito[id_str] + 1 > stock_obj.cantidad_disponible:
                    messages.error(request, f"⚠️ Máximo: {stock_obj.cantidad_disponible} unidades.")
                    return redirect('ver_carrito')
            except Stock.DoesNotExist:
                pass
            carrito[id_str] += 1
        elif accion == 'restar':
            carrito[id_str] -= 1
            if carrito[id_str] <= 0:
                del carrito[id_str]
        elif accion == 'eliminar':
            del carrito[id_str]
    request.session['carrito'] = carrito
    return redirect('ver_carrito')


# ── 6. PAGO ──────────────────────────────────────────────────────────────────
def procesar_pago(request):
    # Si hay una "compra rápida" pendiente, se compra SOLO ese producto
    # (sin tocar el carrito). Si no, se usa el carrito normal.
    comprar_ahora = request.session.get('comprar_ahora') or {}
    es_compra_ahora = bool(comprar_ahora)
    carrito = comprar_ahora if es_compra_ahora else request.session.get('carrito', {})
    if not carrito:
        messages.warning(request, "Tu carrito está vacío.")
        return redirect('catalogo')

    total = 0
    for prod_id, cantidad in carrito.items():
        producto = get_object_or_404(Producto, pk=prod_id)
        total += producto.precio * cantidad

    if not request.user.is_authenticated and request.method == 'GET':
        return render(request, 'pago_opciones.html', {'total': total})

    if request.method == 'POST':
        for prod_id, cantidad in carrito.items():
            prod = get_object_or_404(Producto, pk=prod_id)
            try:
                st = Stock.objects.get(id_producto=prod)
                if cantidad > st.cantidad_disponible:
                    return render(request, 'pago.html', {
                        'total': total,
                        'error': f'El stock de {prod.nombre_producto} acaba de cambiar.',
                    })
            except Stock.DoesNotExist:
                pass

        cliente = None
        if request.user.is_authenticated:
            cliente = Cliente.objects.filter(usuario=request.user).first()
            if not cliente and request.user.email:
                cliente = Cliente.objects.filter(email=request.user.email).first()
                if cliente:
                    cliente.usuario = request.user
                    cliente.save()
            if not cliente:
                nombre = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
                cliente = Cliente.objects.create(
                    usuario=request.user,
                    nombre=nombre,
                    email=None,
                )
        else:
            nombre = request.POST.get('nombre', 'Invitado')
            email = request.POST.get('email', '')
            telefono = request.POST.get('telefono', '')
            if email:
                cliente = Cliente.objects.filter(email=email).first()
                if not cliente:
                    cliente = Cliente.objects.create(
                        nombre=nombre, email=email, telefono=telefono
                    )
            else:
                cliente = Cliente.objects.create(nombre=nombre, telefono=telefono)

        nuevo_pedido = Pedido.objects.create(
            id_cliente=cliente,
            estado_pedido='pendiente',
            tipo_pedido='online',
        )

        for prod_id, cantidad in carrito.items():
            producto = get_object_or_404(Producto, pk=prod_id)
            DetallePedido.objects.create(
                id_pedido=nuevo_pedido,
                id_producto=producto,
                cantidad=cantidad,
                precio_unitario=producto.precio,
            )
            try:
                st = Stock.objects.get(id_producto=producto)
                st.cantidad_disponible -= cantidad
                st.save()
            except Stock.DoesNotExist:
                pass

        # ── Método de pago elegido por el cliente ──
        metodo = (request.POST.get('metodo_pago') or 'Online').strip()
        es_transferencia = metodo.lower() == 'transferencia'

        try:
            pago = Pago.objects.create(
                monto=total,
                metodo_pago=metodo,
                # La transferencia queda PENDIENTE hasta que el local la valide;
                # los demás métodos se aprueban de inmediato.
                estado_pago='Pendiente' if es_transferencia else 'Aprobado',
                fecha_pago=timezone.now().date(),
            )
        except Exception as e:
            pago = None
            print(f"⚠️ Nota Pago: {e}")

        # Si pagó por transferencia, creamos el comprobante para que el
        # administrador/cajero lo valide desde el panel de Transferencias.
        if es_transferencia:
            try:
                Transferencia.objects.create(
                    id_pedido=nuevo_pedido,
                    id_pago=pago,
                    banco='Por informar',
                    numero_operacion=f'WEB-{nuevo_pedido.id_pedido}',
                    rut_pagador=(getattr(cliente, 'rut', None) or ''),
                    monto=total,
                    fecha_transferencia=timezone.now().date(),
                    email_contacto=(getattr(cliente, 'email', None) or None),
                    coincide_monto=True,   # el monto es el total del pedido
                    estado=Transferencia.ESTADO_PENDIENTE,
                )
            except Exception as e:
                print(f"⚠️ Nota Transferencia: {e}")

        # Limpiar lo que se compró: si fue compra rápida, solo eso (el carrito
        # del cliente queda intacto); si no, se vacía el carrito.
        request.session['comprar_ahora'] = {}
        if not es_compra_ahora:
            request.session['carrito'] = {}
        request.session.modified = True
        if es_transferencia:
            messages.success(
                request,
                f"🎉 ¡Pedido #{nuevo_pedido.id_pedido} creado! Realiza la transferencia y "
                f"el local la confirmará pronto. Tu pedido quedará pendiente hasta entonces."
            )
        else:
            messages.success(request, f"🎉 ¡Pedido #{nuevo_pedido.id_pedido} creado! Gracias por tu compra.")

        # ── Correo de comprobante / seguimiento de compra ──
        # fail_silently=True: la compra ya se guardó; un fallo de correo no debe
        # romper la confirmación al cliente.
        email_cliente = getattr(cliente, 'email', None)
        if email_cliente:
            detalles = DetallePedido.objects.filter(id_pedido=nuevo_pedido)
            resumen = "\n".join(
                f"  - {d.cantidad} x {d.id_producto.nombre_producto} (${d.precio_unitario} c/u)"
                for d in detalles
            )
            if es_transferencia:
                estado_txt = (
                    "Tu pedido quedó PENDIENTE. Realiza la transferencia y el local la "
                    "confirmará pronto; te avisaremos por correo cuando esté lista."
                )
            else:
                estado_txt = "Estamos revisando tu compra y te avisaremos cuando esté lista."
            try:
                from django.core.mail import EmailMessage
                pdf = construir_boleta_pdf(nuevo_pedido)
                nota_boleta = "Adjuntamos tu boleta en PDF.\n\n" if pdf else ""
                cuerpo = (
                    f"Hola {getattr(cliente, 'nombre', '') or 'cliente'},\n\n"
                    f"¡Gracias por tu compra! Recibimos tu pedido #{nuevo_pedido.id_pedido}.\n\n"
                    f"Detalle:\n{resumen}\n\n"
                    f"Total: ${total}\n"
                    f"Método de pago: {metodo}\n\n"
                    f"{estado_txt}\n\n"
                    f"{nota_boleta}"
                    f"Un saludo,\nEquipo Librería Chichi"
                )
                correo = EmailMessage(
                    subject=f'Comprobante de tu pedido #{nuevo_pedido.id_pedido} — Librería Chichi',
                    body=cuerpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email_cliente],
                )
                if pdf:
                    correo.attach(f"boleta_pedido_{nuevo_pedido.id_pedido}.pdf", pdf, 'application/pdf')
                correo.send(fail_silently=True)
            except Exception as e:
                print(f"⚠️ No se pudo enviar comprobante de compra: {e}")

        return redirect('inicio')

    cliente_datos = None
    if request.user.is_authenticated:
        cliente_datos = Cliente.objects.filter(usuario=request.user).first()
        if not cliente_datos:
            cliente_datos = type('obj', (object,), {
                'nombre': f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
                'email': request.user.email or '',
                'telefono': '',
            })()

    return render(request, 'pago.html', {'total': total, 'cliente_datos': cliente_datos})


# ── 7. PANEL ADMIN ───────────────────────────────────────────────────────────
def _es_bodeguero(user):
    """Compatibilidad: ahora la lógica de roles vive en permisos.py.
    El bodeguero solo puede ingresar productos nuevos (sin precio ni stock)."""
    return permisos.es_bodeguero(user)


def panel_admin(request):
    if not permisos.es_backoffice(request.user):
        messages.error(request, "Acceso denegado.")
        return redirect('inicio')

    # El cajero trabaja en el Punto de Venta, no en el panel de gestión.
    if permisos.es_cajero(request.user):
        return redirect('panel_pos')

    busqueda = request.GET.get('q', '').strip()
    # Solo productos activos: los "retirados" (con ventas) no llenan el panel.
    productos = Producto.objects.filter(activo=True)
    if busqueda:
        objetivo = _sin_acentos(busqueda)
        productos = [
            p for p in productos
            if objetivo in _sin_acentos(p.nombre_producto)
            or objetivo in _sin_acentos(p.sku or '')
        ]

    for p in productos:
        try:
            stock = Stock.objects.get(id_producto=p)
            p.stock_actual = stock.cantidad_disponible
        except Stock.DoesNotExist:
            p.stock_actual = None

    admins = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True)).distinct()
    # Etiqueta de rol legible para mostrar junto a cada administrador.
    for a in admins:
        a.rol_legible = permisos.rol_legible(a)
        a.rol_key = permisos.rol_key(a)

    es_bodeguero = _es_bodeguero(request.user)

    # Lista COMPLETA (sin filtrar por la búsqueda del inventario) para el
    # buscador en vivo del panel "Actualizar / Reabastecer".
    productos_actualizar = []
    if not es_bodeguero:
        for p in Producto.objects.filter(activo=True).exclude(sku__isnull=True).exclude(sku=''):
            try:
                st = Stock.objects.get(id_producto=p)
                stock_val = st.cantidad_disponible
            except Stock.DoesNotExist:
                stock_val = 0
            productos_actualizar.append({
                'sku': p.sku,
                'nombre': p.nombre_producto,
                'precio': int(p.precio),
                'stock': stock_val,
            })

    # Vista previa del próximo SKU por categoría (para mostrarlo al agregar)
    categorias = [
        'PINTURA Y COLOR', 'PAPEL Y CARTULINA', 'CUADERNOS Y FORROS',
        'LAPICES Y ESCRITURA', 'GEOMETRIA', 'ADHESIVOS Y PEGAMENTOS',
        'MANUALIDADES', 'CARPETERIA', 'OTROS',
    ]
    siguientes_sku = {cat: _siguiente_sku(cat) for cat in categorias}

    context = {
        'productos': productos,
        'productos_actualizar': productos_actualizar,
        'siguientes_sku': siguientes_sku,
        'admins': admins,
        'es_bodeguero': es_bodeguero,
        'busqueda': busqueda,
        'permisos': permisos.permisos_para_template(request.user),
    }
    return render(request, 'panel_admin.html', context)


def admin_agregar_producto(request):
    if not permisos.puede_ingresar_productos(request.user):
        messages.error(request, "No tienes permiso para ingresar productos.")
        return redirect('inicio')
    if request.method != 'POST':
        return redirect('panel_admin')

    nombre = request.POST.get('nombre_producto', '').strip()
    categoria = request.POST.get('categoria', 'OTROS').strip()
    imagen = request.FILES.get('imagen')
    es_bodeguero = _es_bodeguero(request.user)

    if not nombre:
        messages.error(request, "El nombre del producto es obligatorio.")
        return redirect('panel_admin')

    # ── Precio y cantidad entrante: solo admin los maneja ──
    if es_bodeguero:
        precio_ingresado = Decimal('0')
        cantidad_ingresada = 0
    else:
        try:
            precio_ingresado = Decimal(str(request.POST.get('precio', '0') or '0'))
        except InvalidOperation:
            precio_ingresado = Decimal('0')
        try:
            cantidad_ingresada = int(request.POST.get('stock_inicial', 0) or 0)
        except ValueError:
            cantidad_ingresada = 0

    # ── SKU AUTOMÁTICO (se ignora cualquier valor enviado desde el formulario) ──
    sku = _siguiente_sku(categoria)

    # ── Producto NUEVO ──
    prod = Producto.objects.create(
        nombre_producto=nombre,
        sku=sku,
        precio=precio_ingresado,
        categoria=categoria,
        imagen=imagen,
    )
    Stock.objects.create(id_producto=prod, cantidad_disponible=cantidad_ingresada)

    if es_bodeguero:
        messages.success(
            request,
            f"✅ Producto '{nombre}' ingresado con SKU {sku}. Un administrador asignará su precio y stock."
        )
    else:
        messages.success(
            request,
            f"✅ Producto '{nombre}' agregado (SKU {sku}) con {cantidad_ingresada} unidades a ${precio_ingresado:,.0f}."
        )
    return redirect('panel_admin')


def admin_actualizar_producto(request):
    """Actualiza el PRECIO DE VENTA y/o suma stock de un producto buscado por SKU.
    - Si indicas un precio, se fija como nuevo precio de venta (sin promedios).
    - Si indicas una cantidad, se suma al stock actual.
    Puedes cambiar solo el precio, solo el stock, o ambos. Al menos uno es
    obligatorio. Solo administradores (el bodeguero no gestiona stock ni precio)."""
    if not permisos.puede_gestionar_inventario(request.user):
        messages.error(request, "⚠️ No tienes permiso para actualizar stock ni precios.")
        return redirect('panel_admin')
    if request.method != 'POST':
        return redirect('panel_admin')

    sku = request.POST.get('sku', '').strip().upper()
    if not sku:
        messages.error(request, "Debes buscar y seleccionar un producto por su SKU.")
        return redirect('panel_admin')

    producto = Producto.objects.filter(sku=sku).first()
    if not producto:
        messages.error(request, f"No existe ningún producto con el SKU '{sku}'.")
        return redirect('panel_admin')

    # ── Cantidad a sumar (opcional) ──
    try:
        cantidad = int(request.POST.get('stock_inicial', 0) or 0)
    except ValueError:
        cantidad = 0
    if cantidad < 0:
        cantidad = 0

    # ── Nuevo precio de venta (opcional): se fija tal cual, sin promediar ──
    precio_str = (request.POST.get('precio', '') or '').strip()
    nuevo_precio = None
    if precio_str != '':
        try:
            nuevo_precio = Decimal(precio_str)
        except InvalidOperation:
            messages.error(request, "El precio ingresado no es válido.")
            return redirect('panel_admin')
        if nuevo_precio < 0:
            messages.error(request, "El precio no puede ser negativo.")
            return redirect('panel_admin')

    if cantidad <= 0 and nuevo_precio is None:
        messages.error(request, "Indica un nuevo precio de venta o una cantidad a sumar (o ambos).")
        return redirect('panel_admin')

    stock_obj, _ = Stock.objects.get_or_create(
        id_producto=producto, defaults={'cantidad_disponible': 0}
    )
    cant_actual = stock_obj.cantidad_disponible
    precio_anterior = Decimal(str(producto.precio))

    partes = []
    if nuevo_precio is not None:
        producto.precio = nuevo_precio
        producto.save()
        partes.append(f"precio ${precio_anterior:,.0f} → ${nuevo_precio:,.0f}")
    if cantidad > 0:
        stock_obj.cantidad_disponible = cant_actual + cantidad
        stock_obj.save()
        partes.append(f"stock {cant_actual} + {cantidad} = {cant_actual + cantidad}")

    messages.success(
        request,
        f"✅ '{producto.nombre_producto}' actualizado: " + " · ".join(partes) + "."
    )
    return redirect('panel_admin')



def admin_editar_producto(request, producto_id):
    # El bodeguero y el cajero no editan precios ni stock: lo gestiona un admin.
    if not permisos.puede_gestionar_inventario(request.user):
        messages.error(request, "⚠️ No tienes permiso para editar productos. Lo gestiona un administrador.")
        return redirect('panel_admin')

    producto = get_object_or_404(Producto, pk=producto_id)

    if request.method == 'POST':
        nombre = request.POST.get('nombre_producto', '').strip()
        precio_nuevo = request.POST.get('precio')
        categoria = request.POST.get('categoria', '').strip()
        stock_nuevo = request.POST.get('stock')
        imagen = request.FILES.get('imagen')

        if nombre:
            producto.nombre_producto = nombre
        if categoria:
            producto.categoria = categoria
        if imagen:
            producto.imagen = imagen

        # El SKU NO se edita: es automático y fijo. Se ignora cualquier valor enviado.

        # Precio: edición directa (sin promedios; eso es solo al reabastecer por SKU)
        if precio_nuevo not in (None, ''):
            try:
                producto.precio = Decimal(str(precio_nuevo))
            except InvalidOperation:
                messages.error(request, "El precio ingresado no es válido.")
                return redirect('panel_admin')

        producto.save()

        # Stock: se fija directamente al valor indicado
        if stock_nuevo is not None and stock_nuevo != '':
            try:
                cantidad = int(stock_nuevo)
            except ValueError:
                cantidad = 0
            st, _ = Stock.objects.get_or_create(
                id_producto=producto, defaults={'cantidad_disponible': 0}
            )
            st.cantidad_disponible = cantidad
            st.save()

        if not list(messages.get_messages(request)):
            messages.success(request, "✅ Producto actualizado.")

    return redirect('panel_admin')


def admin_eliminar_producto(request, producto_id):
    if not permisos.puede_eliminar_producto(request.user):
        messages.error(request, "Solo el super-administrador puede eliminar productos.")
        return redirect('panel_admin')
    producto = get_object_or_404(Producto, pk=producto_id)
    nombre = producto.nombre_producto

    # Si el producto ya aparece en algún pedido, NO se puede borrar físicamente:
    # la BD usa on_delete=RESTRICT en DetallePedido y lanzaría un error 500.
    # En su lugar lo retiramos de la tienda (borrado lógico) y conservamos el
    # historial de ventas.
    if DetallePedido.objects.filter(id_producto=producto).exists():
        producto.activo = False
        producto.save()
        messages.success(
            request,
            f"🗑️ '{nombre}' fue retirado de la tienda. Se conservó porque tiene "
            f"pedidos asociados; ya no aparece en el catálogo."
        )
        return redirect('panel_admin')

    # No tiene pedidos → se puede borrar de verdad. Aun así protegemos contra
    # cualquier otra relación inesperada para no romper la página.
    try:
        producto.delete()
        messages.success(request, f"🗑️ '{nombre}' eliminado.")
    except (RestrictedError, ProtectedError):
        producto.activo = False
        producto.save()
        messages.success(
            request,
            f"🗑️ '{nombre}' fue retirado de la tienda (tenía datos asociados; "
            f"se conservó el historial)."
        )
    return redirect('panel_admin')


def admin_crear_subadmin(request):
    if not permisos.puede_gestionar_admins(request.user):
        messages.error(request, "Solo el super-administrador puede crear otros administradores.")
        return redirect('panel_admin')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        password_confirm = request.POST.get('password_confirm', '').strip()
        rol = request.POST.get('rol', 'bodeguero')

        if not username or not password:
            messages.error(request, "Usuario y contraseña son obligatorios.")
            return redirect('panel_admin')
        if password != password_confirm:
            messages.error(request, "Las contraseñas no coinciden. Verifícalas e inténtalo de nuevo.")
            return redirect('panel_admin')
        if len(password) < 8:
            messages.error(request, "La contraseña debe tener al menos 8 caracteres.")
            return redirect('panel_admin')
        if User.objects.filter(username=username).exists():
            messages.error(request, f"El usuario '{username}' ya existe.")
            return redirect('panel_admin')

        # Garantizar que los grupos y permisos existan antes de asignar.
        permisos.configurar_roles()
        from django.contrib.auth.models import Group

        nuevo_admin = User.objects.create_user(username=username, email=email, password=password)
        nuevo_admin.is_staff = True          # todos los roles internos acceden al panel
        nuevo_admin.is_superuser = False
        nuevo_admin.user_permissions.clear()  # los permisos vienen del grupo
        nuevo_admin.groups.clear()

        # Mapa de rol → grupo de la librería
        grupos_por_rol = {
            'admin_completo': permisos.GRUPO_ADMIN,
            'cajero': permisos.GRUPO_CAJERO,
            'bodeguero': permisos.GRUPO_BODEGUERO,
        }

        if rol == 'super_admin':
            # Super admin: control total, incluso crear más admins.
            nuevo_admin.is_superuser = True
        else:
            nombre_grupo = grupos_por_rol.get(rol, permisos.GRUPO_BODEGUERO)
            grupo = Group.objects.get(name=nombre_grupo)
            nuevo_admin.groups.add(grupo)

        nuevo_admin.save()
        etiquetas = {
            'super_admin': 'Super Admin',
            'admin_completo': 'Administrador',
            'cajero': 'Cajero',
            'bodeguero': 'Bodeguero',
        }
        messages.success(request, f"✅ Usuario '{username}' creado con rol: {etiquetas.get(rol, rol)}.")
    return redirect('panel_admin')


def iniciar_sesion_admin(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('panel_admin')
        return redirect('inicio')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_staff:
            login(request, user)
            messages.success(request, f"¡Bienvenido al panel, {user.first_name or user.username}!")
            return redirect('panel_admin')
        elif user is not None and not user.is_staff:
            messages.error(request, "Esta cuenta no tiene permisos de administrador.")
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")

    return render(request, 'login_admin.html', {})

# ── 8. PANEL DE PEDIDOS / ENVÍOS ─────────────────────────────────────────────
ESTADOS_PEDIDO = ['pendiente', 'confirmado', 'listo', 'entregado', 'cancelado']


def panel_pedidos(request):
    # Los pedidos/envíos los gestiona el administrador, no el cajero ni el bodeguero.
    if not permisos.puede_gestionar_pedidos(request.user):
        messages.error(request, "No tienes acceso a los pedidos.")
        return redirect('inicio' if not permisos.es_backoffice(request.user) else 'panel_admin')

    filtro = request.GET.get('estado', '').strip().lower()

    pedidos = Pedido.objects.select_related('id_cliente').order_by('-id_pedido')
    if filtro in ESTADOS_PEDIDO:
        pedidos = pedidos.filter(estado_pedido=filtro)

    # Conteos por estado (para las pestañas)
    conteos = {est: Pedido.objects.filter(estado_pedido=est).count() for est in ESTADOS_PEDIDO}
    conteos['todos'] = Pedido.objects.count()

    lista = []
    for ped in pedidos:
        detalles = DetallePedido.objects.select_related('id_producto').filter(id_pedido=ped)
        items = []
        total = Decimal('0')
        for d in detalles:
            subtotal = Decimal(str(d.precio_unitario)) * d.cantidad
            total += subtotal
            items.append({
                'nombre': d.id_producto.nombre_producto,
                'sku': d.id_producto.sku or '—',
                'cantidad': d.cantidad,
                'precio_unitario': int(d.precio_unitario),
                'subtotal': int(subtotal),
            })
        cli = ped.id_cliente
        # ¿Tiene una transferencia aún sin validar?
        transf_pendiente = ped.transferencias.filter(
            estado=Transferencia.ESTADO_PENDIENTE
        ).exists()
        lista.append({
            'id': ped.id_pedido,
            'fecha': ped.fecha_pedido,
            'estado': ped.estado_pedido,
            'tipo': ped.tipo_pedido,
            'transf_pendiente': transf_pendiente,
            'cliente': {
                'nombre': cli.nombre,
                'email': cli.email or '—',
                'telefono': cli.telefono or '—',
                'rut': cli.rut or '—',
                'direccion': cli.direccion_facturacion or '—',
            },
            'items': items,
            'total': int(total),
            'n_items': len(items),
        })

    return render(request, 'panel_pedidos.html', {
        'pedidos': lista,
        'filtro': filtro or 'todos',
        'conteos': conteos,
        'es_super': request.user.is_superuser,
        'permisos': permisos.permisos_para_template(request.user),
    })


def cambiar_estado_pedido(request, pedido_id):
    if not permisos.puede_gestionar_pedidos(request.user):
        messages.error(request, "No tienes acceso a los pedidos.")
        return redirect('inicio' if not permisos.es_backoffice(request.user) else 'panel_admin')
    if request.method != 'POST':
        return redirect('panel_pedidos')

    pedido = get_object_or_404(Pedido, pk=pedido_id)
    accion = request.POST.get('accion', '')

    # Si el pedido se pagó por transferencia y aún no se valida, no se puede
    # confirmar ni entregar: primero hay que aprobar la transferencia.
    transf_pendiente = pedido.transferencias.filter(
        estado=Transferencia.ESTADO_PENDIENTE
    ).exists()
    if accion in ('confirmar', 'entregar', 'listo') and transf_pendiente:
        messages.error(
            request,
            "⚠️ Este pedido se pagó por transferencia y aún no la validas. "
            "Ve al panel de Transferencias y apruébala primero."
        )
        estado = request.POST.get('volver_estado', '')
        from django.urls import reverse
        url = reverse('panel_pedidos')
        if estado and estado != 'todos':
            url += f"?estado={estado}"
        return redirect(url)

    if accion == 'confirmar':
        pedido.estado_pedido = 'confirmado'
        pedido.save()
        enviar_correo_estado_pedido(pedido, 'confirmado')
        messages.success(request, f"✅ Pedido #{pedido.id_pedido} confirmado. Se notificó al cliente por correo.")

    elif accion == 'listo':
        pedido.estado_pedido = 'listo'
        pedido.save()
        enviar_correo_estado_pedido(pedido, 'listo')
        messages.success(request, f"📦 Pedido #{pedido.id_pedido} marcado como listo para entrega. Se notificó al cliente por correo.")

    elif accion == 'entregar':
        pedido.estado_pedido = 'entregado'
        pedido.save()
        enviar_correo_estado_pedido(pedido, 'entregado')
        messages.success(request, f"📦 Pedido #{pedido.id_pedido} marcado como retirado. Se notificó al cliente por correo.")

    elif accion == 'cancelar':
        motivo = (request.POST.get('motivo', '') or '').strip() or None
        # Devolver el stock de cada producto del pedido (si no estaba ya cancelado)
        if pedido.estado_pedido != 'cancelado':
            for d in DetallePedido.objects.select_related('id_producto').filter(id_pedido=pedido):
                try:
                    st = Stock.objects.get(id_producto=d.id_producto)
                    st.cantidad_disponible += d.cantidad
                    st.save()
                except Stock.DoesNotExist:
                    pass
            # Marcar como reembolsado el pago de las transferencias validadas
            # (es el único pago que queda enlazado al pedido en este sistema).
            for t in pedido.transferencias.all():
                if t.id_pago and t.id_pago.estado_pago != 'Reembolsado':
                    t.id_pago.estado_pago = 'Reembolsado'
                    t.id_pago.save()
        pedido.estado_pedido = 'cancelado'
        pedido.save()
        enviar_correo_estado_pedido(pedido, 'cancelado', motivo=motivo)
        messages.success(
            request,
            f"↩️ Pedido #{pedido.id_pedido} cancelado, stock devuelto y cliente notificado del reembolso por correo."
        )

    else:
        messages.error(request, "Acción no válida.")

    estado = request.POST.get('volver_estado', '')
    from django.urls import reverse
    url = reverse('panel_pedidos')
    if estado and estado != 'todos':
        url += f"?estado={estado}"
    return redirect(url)


# ── 9. BOLETA (PDF) ──────────────────────────────────────────────────────────
# Datos del local para la boleta. Edítalos con los datos reales de la librería.
DATOS_LOCAL = {
    'nombre': getattr(settings, 'TIENDA_NOMBRE', 'Librería Chichi'),
    'rut': getattr(settings, 'TIENDA_RUT', ''),
    'giro': getattr(settings, 'TIENDA_GIRO', ''),
    'direccion': getattr(settings, 'TIENDA_DIRECCION', ''),
    'telefono': getattr(settings, 'TIENDA_TELEFONO', ''),
}


def _formato_clp(valor):
    """Formatea un entero como pesos chilenos: 1234567 -> '1.234.567'."""
    return f"{int(valor):,}".replace(",", ".")


def construir_boleta_pdf(pedido):
    """Construye el PDF de la boleta de un pedido y devuelve los bytes.
    Devuelve None si no está instalada la librería 'reportlab'."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        )
    except ImportError:
        return None

    import io

    detalles = DetallePedido.objects.select_related('id_producto').filter(id_pedido=pedido)
    cli = pedido.id_cliente

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Boleta pedido {pedido.id_pedido}",
    )

    styles = getSampleStyleSheet()
    MAGENTA = colors.HexColor('#e8007d')
    VIOLET = colors.HexColor('#7c3aed')
    GRIS = colors.HexColor('#555555')

    est_titulo = ParagraphStyle('titulo', parent=styles['Title'], fontSize=20,
                                textColor=MAGENTA, spaceAfter=2)
    est_sub = ParagraphStyle('sub', parent=styles['Normal'], fontSize=9, textColor=GRIS)
    est_normal = ParagraphStyle('n', parent=styles['Normal'], fontSize=10, leading=14)
    est_dato = ParagraphStyle('d', parent=styles['Normal'], fontSize=9.5, leading=14)
    est_h = ParagraphStyle('h', parent=styles['Normal'], fontSize=11,
                           textColor=VIOLET, spaceBefore=8, spaceAfter=4, fontName='Helvetica-Bold')

    elems = []

    # Encabezado del local
    elems.append(Paragraph(DATOS_LOCAL['nombre'], est_titulo))
    elems.append(Paragraph(
        f"{DATOS_LOCAL['giro']}<br/>"
        f"RUT: {DATOS_LOCAL['rut']} · {DATOS_LOCAL['direccion']}<br/>"
        f"Tel: {DATOS_LOCAL['telefono']}", est_sub))
    elems.append(Spacer(1, 6 * mm))

    # Recuadro boleta
    cabecera = [
        [Paragraph("<b>BOLETA ELECTRÓNICA</b>", est_normal),
         Paragraph(f"<b>N° {pedido.id_pedido:06d}</b>", est_normal)],
        [Paragraph(f"Fecha: {pedido.fecha_pedido}", est_dato),
         Paragraph(f"Estado: {pedido.estado_pedido}", est_dato)],
    ]
    t_cab = Table(cabecera, colWidths=[None, 55 * mm])
    t_cab.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.8, VIOLET),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f4ecff')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elems.append(t_cab)
    elems.append(Spacer(1, 5 * mm))

    # Datos del cliente
    elems.append(Paragraph("Datos del cliente", est_h))
    elems.append(Paragraph(
        f"<b>Nombre:</b> {cli.nombre}<br/>"
        f"<b>RUT:</b> {cli.rut or '—'}<br/>"
        f"<b>Email:</b> {cli.email or '—'} · <b>Tel:</b> {cli.telefono or '—'}<br/>"
        f"<b>Dirección:</b> {cli.direccion_facturacion or '—'}", est_dato))
    elems.append(Spacer(1, 5 * mm))

    # Detalle de productos
    elems.append(Paragraph("Detalle", est_h))
    data = [['Producto', 'SKU', 'Cant.', 'P. unit.', 'Subtotal']]
    total = 0
    for d in detalles:
        sub = int(d.precio_unitario) * d.cantidad
        total += sub
        data.append([
            Paragraph(d.id_producto.nombre_producto, est_dato),
            d.id_producto.sku or '—',
            str(d.cantidad),
            f"${_formato_clp(d.precio_unitario)}",
            f"${_formato_clp(sub)}",
        ])
    data.append(['', '', '', 'TOTAL', f"${_formato_clp(total)}"])

    tabla = Table(data, colWidths=[None, 28 * mm, 14 * mm, 24 * mm, 26 * mm])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), VIOLET),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f7f7fb')]),
        ('LINEBELOW', (0, 0), (-1, -2), 0.4, colors.HexColor('#dddddd')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        # Fila total
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f4ecff')),
        ('FONTNAME', (3, -1), (-1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (4, -1), (-1, -1), MAGENTA),
        ('FONTSIZE', (3, -1), (-1, -1), 11),
        ('LINEABOVE', (0, -1), (-1, -1), 0.8, VIOLET),
    ]))
    elems.append(tabla)
    elems.append(Spacer(1, 10 * mm))
    elems.append(Paragraph(
        "Gracias por su compra. Este documento es un comprobante interno emitido por el sistema.",
        est_sub))

    doc.build(elems)
    buffer.seek(0)
    return buffer.getvalue()


def generar_boleta(request, pedido_id):
    """Vista: descarga la boleta en PDF (solo backoffice)."""
    if not permisos.puede_generar_boleta(request.user):
        messages.error(request, "No tienes acceso a las boletas.")
        return redirect('inicio' if not permisos.es_backoffice(request.user) else 'panel_admin')

    pedido = get_object_or_404(Pedido, pk=pedido_id)
    pdf = construir_boleta_pdf(pedido)
    if pdf is None:
        messages.error(
            request,
            "Falta la librería 'reportlab' para generar boletas. "
            "Instálala con: pip install reportlab"
        )
        return redirect('panel_pedidos')

    from django.http import HttpResponse
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="boleta_pedido_{pedido.id_pedido}.pdf"'
    return response


# ── 10. DASHBOARD DE VENTAS / GANANCIAS ──────────────────────────────────────
# Una "venta realizada" es un pedido confirmado o entregado (no pendiente ni cancelado).
ESTADOS_VENTA = ['confirmado', 'entregado']


def _resumen_periodo(detalles):
    """Recibe un iterable de DetallePedido y devuelve totales."""
    pedidos = set()
    unidades = 0
    ingresos = 0
    for d in detalles:
        pedidos.add(d.id_pedido_id)
        unidades += d.cantidad
        ingresos += int(d.precio_unitario) * d.cantidad
    return {'n_ventas': len(pedidos), 'unidades': unidades, 'ingresos': ingresos}


def panel_ventas(request):
    # Reportes de ventas: administrador y super administrador.
    if not permisos.puede_ver_reportes(request.user):
        messages.error(request, "No tienes permiso para ver el historial de ventas.")
        return redirect('inicio' if not permisos.es_backoffice(request.user) else 'panel_admin')

    hoy = timezone.localdate()
    inicio_semana = hoy - timezone.timedelta(days=hoy.weekday())   # lunes
    inicio_mes = hoy.replace(day=1)

    # Todos los detalles de ventas realizadas (una sola consulta)
    detalles = list(
        DetallePedido.objects
        .select_related('id_pedido', 'id_producto')
        .filter(id_pedido__estado_pedido__in=ESTADOS_VENTA)
    )

    # ¿Drill-down a un día específico?  ?dia=YYYY-MM-DD
    dia_str = request.GET.get('dia', '').strip()
    dia_detalle = None
    if dia_str:
        try:
            from datetime import datetime
            dia_sel = datetime.strptime(dia_str, '%Y-%m-%d').date()
            del_dia = [d for d in detalles if d.id_pedido.fecha_pedido == dia_sel]
            prods = {}
            for d in del_dia:
                k = d.id_producto_id
                if k not in prods:
                    prods[k] = {'nombre': d.id_producto.nombre_producto,
                                'sku': d.id_producto.sku or '—', 'unidades': 0, 'ingresos': 0}
                prods[k]['unidades'] += d.cantidad
                prods[k]['ingresos'] += int(d.precio_unitario) * d.cantidad
            dia_detalle = {
                'fecha': dia_sel,
                'resumen': _resumen_periodo(del_dia),
                'productos': sorted(prods.values(), key=lambda x: -x['unidades']),
            }
        except ValueError:
            dia_detalle = None

    # Período para el desglose de productos:  hoy | semana | mes | todo
    periodo = request.GET.get('periodo', 'hoy').strip()
    if periodo == 'semana':
        det_periodo = [d for d in detalles if d.id_pedido.fecha_pedido >= inicio_semana]
        etiqueta_periodo = 'Esta semana'
    elif periodo == 'mes':
        det_periodo = [d for d in detalles if d.id_pedido.fecha_pedido >= inicio_mes]
        etiqueta_periodo = 'Este mes'
    elif periodo == 'todo':
        det_periodo = detalles
        etiqueta_periodo = 'Histórico completo'
    else:
        periodo = 'hoy'
        det_periodo = [d for d in detalles if d.id_pedido.fecha_pedido == hoy]
        etiqueta_periodo = 'Hoy'

    # Tarjetas resumen
    resumen_hoy = _resumen_periodo([d for d in detalles if d.id_pedido.fecha_pedido == hoy])
    resumen_semana = _resumen_periodo([d for d in detalles if d.id_pedido.fecha_pedido >= inicio_semana])
    resumen_mes = _resumen_periodo([d for d in detalles if d.id_pedido.fecha_pedido >= inicio_mes])
    resumen_total = _resumen_periodo(detalles)

    # Desglose de productos del período seleccionado
    prods = {}
    for d in det_periodo:
        k = d.id_producto_id
        if k not in prods:
            prods[k] = {'nombre': d.id_producto.nombre_producto,
                        'sku': d.id_producto.sku or '—', 'unidades': 0, 'ingresos': 0}
        prods[k]['unidades'] += d.cantidad
        prods[k]['ingresos'] += int(d.precio_unitario) * d.cantidad
    productos_periodo = sorted(prods.values(), key=lambda x: -x['ingresos'])

    # Desglose por canal (online vs presencial) del período seleccionado
    resumen_online = _resumen_periodo([d for d in det_periodo if d.id_pedido.tipo_pedido == 'online'])
    resumen_presencial = _resumen_periodo([d for d in det_periodo if d.id_pedido.tipo_pedido == 'presencial'])

    # Histórico día a día
    por_dia = {}
    for d in detalles:
        f = d.id_pedido.fecha_pedido
        if f not in por_dia:
            por_dia[f] = {'pedidos': set(), 'unidades': 0, 'ingresos': 0}
        por_dia[f]['pedidos'].add(d.id_pedido_id)
        por_dia[f]['unidades'] += d.cantidad
        por_dia[f]['ingresos'] += int(d.precio_unitario) * d.cantidad
    dias = [{'fecha': f, 'n_ventas': len(v['pedidos']), 'unidades': v['unidades'], 'ingresos': v['ingresos']}
            for f, v in por_dia.items()]
    dias.sort(key=lambda x: x['fecha'], reverse=True)

    # Histórico semana a semana (por número de semana ISO)
    por_semana = {}
    for d in detalles:
        f = d.id_pedido.fecha_pedido
        iso = f.isocalendar()
        clave = (iso[0], iso[1])
        if clave not in por_semana:
            lunes = f - timezone.timedelta(days=f.weekday())
            por_semana[clave] = {'inicio': lunes, 'fin': lunes + timezone.timedelta(days=6),
                                 'pedidos': set(), 'unidades': 0, 'ingresos': 0}
        por_semana[clave]['pedidos'].add(d.id_pedido_id)
        por_semana[clave]['unidades'] += d.cantidad
        por_semana[clave]['ingresos'] += int(d.precio_unitario) * d.cantidad
    semanas = [{'inicio': v['inicio'], 'fin': v['fin'], 'anio': k[0], 'semana': k[1],
                'n_ventas': len(v['pedidos']), 'unidades': v['unidades'], 'ingresos': v['ingresos']}
               for k, v in por_semana.items()]
    semanas.sort(key=lambda x: (x['anio'], x['semana']), reverse=True)

    # Gráfico de los últimos 7 días (ingresos)
    grafico = []
    max_ing = 1
    for i in range(6, -1, -1):
        f = hoy - timezone.timedelta(days=i)
        ing = por_dia.get(f, {}).get('ingresos', 0)
        max_ing = max(max_ing, ing)
        grafico.append({'fecha': f, 'ingresos': ing})
    for g in grafico:
        g['pct'] = round(g['ingresos'] * 100 / max_ing) if max_ing else 0

    # Formatear montos a pesos chilenos (con puntos de miles) para mostrar
    def fmt(v):
        return f"{int(v):,}".replace(",", ".")

    for r in (resumen_hoy, resumen_semana, resumen_mes, resumen_total):
        r['ingresos_fmt'] = fmt(r['ingresos'])
    for r in (resumen_online, resumen_presencial):
        r['ingresos_fmt'] = fmt(r['ingresos'])
    for p in productos_periodo:
        p['ingresos_fmt'] = fmt(p['ingresos'])
    for d in dias:
        d['ingresos_fmt'] = fmt(d['ingresos'])
    for s in semanas:
        s['ingresos_fmt'] = fmt(s['ingresos'])
    for g in grafico:
        g['ingresos_fmt'] = fmt(g['ingresos'])
    if dia_detalle:
        dia_detalle['resumen']['ingresos_fmt'] = fmt(dia_detalle['resumen']['ingresos'])
        for p in dia_detalle['productos']:
            p['ingresos_fmt'] = fmt(p['ingresos'])

    return render(request, 'panel_ventas.html', {
        'hoy': hoy,
        'resumen_hoy': resumen_hoy,
        'resumen_semana': resumen_semana,
        'resumen_mes': resumen_mes,
        'resumen_total': resumen_total,
        'productos_periodo': productos_periodo,
        'resumen_online': resumen_online,
        'resumen_presencial': resumen_presencial,
        'periodo': periodo,
        'etiqueta_periodo': etiqueta_periodo,
        'dias': dias,
        'semanas': semanas,
        'grafico': grafico,
        'dia_detalle': dia_detalle,
        'permisos': permisos.permisos_para_template(request.user),
    })


# ── 11. ELIMINAR PERFIL DE ADMINISTRADOR (solo super admin) ──────────────────
def admin_eliminar_subadmin(request, user_id):
    if not request.user.is_superuser:
        messages.error(request, "Solo el super-administrador puede eliminar perfiles.")
        return redirect('panel_admin')
    if request.method != 'POST':
        return redirect('panel_admin')

    objetivo = get_object_or_404(User, pk=user_id)

    # No puedes eliminarte a ti mismo
    if objetivo.id == request.user.id:
        messages.error(request, "No puedes eliminar tu propia cuenta.")
        return redirect('panel_admin')

    # No dejar el sistema sin ningún super administrador
    if objetivo.is_superuser and User.objects.filter(is_superuser=True).count() <= 1:
        messages.error(request, "No puedes eliminar al último super administrador.")
        return redirect('panel_admin')

    nombre = objetivo.username
    objetivo.delete()
    messages.success(request, f"🗑️ Perfil '{nombre}' eliminado correctamente.")
    return redirect('panel_admin')


# ── 11b. EDITAR PERFIL DE ADMINISTRADOR (solo super admin) ───────────────────
def admin_editar_subadmin(request, user_id):
    if not permisos.puede_gestionar_admins(request.user):
        messages.error(request, "Solo el super-administrador puede editar perfiles.")
        return redirect('panel_admin')
    if request.method != 'POST':
        return redirect('panel_admin')

    objetivo = get_object_or_404(User, pk=user_id)
    email = request.POST.get('email', '').strip()
    rol = request.POST.get('rol', '').strip()
    password = request.POST.get('password', '').strip()
    password_confirm = request.POST.get('password_confirm', '').strip()

    # ── Cambio de contraseña (opcional): solo si escribió algo ──
    if password or password_confirm:
        if password != password_confirm:
            messages.error(request, "Las contraseñas no coinciden.")
            return redirect('panel_admin')
        if len(password) < 8:
            messages.error(request, "La nueva contraseña debe tener al menos 8 caracteres.")
            return redirect('panel_admin')
        objetivo.set_password(password)

    # ── Correo ──
    objetivo.email = email

    # ── Rol (con resguardo: no dejar el sistema sin super admin) ──
    permisos.configurar_roles()
    from django.contrib.auth.models import Group
    grupos_por_rol = {
        'admin_completo': permisos.GRUPO_ADMIN,
        'cajero': permisos.GRUPO_CAJERO,
        'bodeguero': permisos.GRUPO_BODEGUERO,
    }
    es_ultimo_super = objetivo.is_superuser and User.objects.filter(is_superuser=True).count() <= 1

    if rol and rol != permisos.rol_key(objetivo):
        if es_ultimo_super and rol != 'super_admin':
            messages.error(request, "No puedes quitarle el rol al único super administrador.")
            return redirect('panel_admin')
        objetivo.groups.clear()
        objetivo.user_permissions.clear()
        if rol == 'super_admin':
            objetivo.is_superuser = True
            objetivo.is_staff = True
        else:
            objetivo.is_superuser = False
            objetivo.is_staff = True
            grupo = Group.objects.get(name=grupos_por_rol.get(rol, permisos.GRUPO_BODEGUERO))
            objetivo.groups.add(grupo)

    objetivo.save()

    # Si me cambié MI propia contraseña, mantener la sesión iniciada
    if password and objetivo.id == request.user.id:
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, objetivo)

    messages.success(request, f"✅ Perfil '{objetivo.username}' actualizado correctamente.")
    return redirect('panel_admin')


# ── 12. PUNTO DE VENTA (POS) — ventas presenciales en el local ───────────────
def panel_pos(request):
    if not permisos.puede_usar_pos(request.user):
        messages.error(request, "No tienes acceso al punto de venta.")
        return redirect('inicio' if not permisos.es_backoffice(request.user) else 'panel_admin')

    productos = []
    for p in Producto.objects.all():
        try:
            stock = Stock.objects.get(id_producto=p).cantidad_disponible
        except Stock.DoesNotExist:
            stock = 0
        productos.append({
            'id': p.id_producto,
            'nombre': p.nombre_producto,
            'sku': p.sku or '',
            'precio': int(p.precio),
            'stock': stock,
        })

    return render(request, 'panel_pos.html', {
        'productos_json': productos,
        'es_super': request.user.is_superuser,
        'permisos': permisos.permisos_para_template(request.user),
        'boleta_id': request.GET.get('boleta'),
    })


def registrar_venta_pos(request):
    if not permisos.puede_usar_pos(request.user):
        messages.error(request, "No tienes acceso al punto de venta.")
        return redirect('inicio' if not permisos.es_backoffice(request.user) else 'panel_admin')
    if request.method != 'POST':
        return redirect('panel_pos')

    import json
    try:
        items = json.loads(request.POST.get('items', '[]'))
    except (ValueError, TypeError):
        items = []

    metodo = request.POST.get('metodo_pago', '').strip()
    metodos_validos = ['Efectivo', 'Tarjeta', 'Transferencia']
    if metodo not in metodos_validos:
        messages.error(request, "Debes seleccionar un método de pago válido.")
        return redirect('panel_pos')

    if not items:
        messages.error(request, "No agregaste productos a la venta.")
        return redirect('panel_pos')

    # Validar stock de todos los productos antes de registrar nada
    validados = []
    total = 0
    for it in items:
        try:
            prod = Producto.objects.get(pk=it.get('id'))
            cant = int(it.get('cantidad', 0))
        except (Producto.DoesNotExist, ValueError, TypeError):
            continue
        if cant < 1:
            continue
        try:
            st = Stock.objects.get(id_producto=prod)
            disponible = st.cantidad_disponible
        except Stock.DoesNotExist:
            st = None
            disponible = 0
        if cant > disponible:
            messages.error(request, f"Stock insuficiente de {prod.nombre_producto} (quedan {disponible}).")
            return redirect('panel_pos')
        validados.append((prod, cant, st))
        total += int(prod.precio) * cant

    if not validados:
        messages.error(request, "No hay productos válidos en la venta.")
        return redirect('panel_pos')

    # Cliente único de mostrador para ventas presenciales
    cliente, _ = Cliente.objects.get_or_create(
        email='mostrador@libreriachichi.local',
        defaults={'nombre': 'Venta Presencial (Mostrador)'}
    )

    # Pedido marcado como ENTREGADO de inmediato y tipo PRESENCIAL
    pedido = Pedido.objects.create(
        id_cliente=cliente,
        estado_pedido='entregado',
        tipo_pedido='presencial',
    )
    for prod, cant, st in validados:
        DetallePedido.objects.create(
            id_pedido=pedido, id_producto=prod,
            cantidad=cant, precio_unitario=prod.precio,
        )
        if st:
            st.cantidad_disponible -= cant
            st.save()

    Pago.objects.create(monto=total, metodo_pago=metodo, estado_pago='Aprobado')

    messages.success(
        request,
        f"✅ Venta presencial #{pedido.id_pedido} registrada por ${_formato_clp(total)}, pagada con {metodo}."
    )
    from django.urls import reverse
    return redirect(f"{reverse('panel_pos')}?boleta={pedido.id_pedido}")


# ── 11. PANEL DE TRANSFERENCIAS ──────────────────────────────────────────────
def panel_transferencias(request):
    """Pantalla para revisar y validar transferencias bancarias.
    Accesible para quien pueda validar (super, administrador o cajero)."""
    if not permisos.puede_validar_transferencias(request.user):
        messages.error(request, "No tienes permiso para validar transferencias.")
        return redirect('inicio' if not permisos.es_backoffice(request.user) else 'panel_admin')

    from .api import total_pedido

    filtro = request.GET.get('estado', 'pendiente').strip().lower()
    qs = Transferencia.objects.select_related('id_pedido').all()
    if filtro in (Transferencia.ESTADO_PENDIENTE, Transferencia.ESTADO_VALIDADA,
                  Transferencia.ESTADO_RECHAZADA):
        qs = qs.filter(estado=filtro)

    lista = []
    for t in qs:
        lista.append({
            'id': t.id_transferencia,
            'pedido_id': t.id_pedido_id,
            'banco': t.banco,
            'numero_operacion': t.numero_operacion,
            'rut_pagador': t.rut_pagador,
            'monto': int(t.monto),
            'monto_esperado': int(total_pedido(t.id_pedido)),
            'coincide_monto': t.coincide_monto,
            'fecha': t.fecha_transferencia,
            'estado': t.estado,
            'motivo_rechazo': t.motivo_rechazo,
        })

    conteos = {
        'pendiente': Transferencia.objects.filter(estado='pendiente').count(),
        'validada': Transferencia.objects.filter(estado='validada').count(),
        'rechazada': Transferencia.objects.filter(estado='rechazada').count(),
    }

    return render(request, 'panel_transferencias.html', {
        'transferencias': lista,
        'filtro': filtro,
        'conteos': conteos,
        'permisos': permisos.permisos_para_template(request.user),
    })


# ── 12. MI PERFIL (cliente / persona natural) ────────────────────────────────
def mi_perfil(request):
    """Permite a un cliente autenticado ver y modificar sus datos."""
    if not request.user.is_authenticated:
        messages.error(request, "Debes iniciar sesión para ver tu perfil.")
        return redirect('login')

    # Aseguramos que exista una ficha de Cliente enlazada a este usuario.
    cliente = Cliente.objects.filter(usuario=request.user).first()
    if cliente is None:
        cliente = Cliente.objects.create(
            usuario=request.user,
            rut=request.user.username,
            nombre=f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
            email=request.user.email or None,
        )

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        email = request.POST.get('email', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        direccion = request.POST.get('direccion', '').strip()

        # ── Cambio de contraseña (opcional: solo si llena los campos) ──
        actual = request.POST.get('password_actual', '')
        nueva = request.POST.get('nueva_password', '')
        confirmar = request.POST.get('confirmar_password', '')
        if nueva or confirmar or actual:
            if not request.user.check_password(actual):
                messages.error(request, "Tu contraseña actual no es correcta.")
                return redirect('mi_perfil')
            if len(nueva) < 8:
                messages.error(request, "La nueva contraseña debe tener al menos 8 caracteres.")
                return redirect('mi_perfil')
            if nueva != confirmar:
                messages.error(request, "La nueva contraseña y su confirmación no coinciden.")
                return redirect('mi_perfil')
            request.user.set_password(nueva)
            request.user.save()
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)  # no cerrar la sesión
            messages.success(request, "🔒 Tu contraseña fue actualizada.")

        # ── Datos personales ──
        if not nombre:
            messages.error(request, "El nombre no puede quedar vacío.")
            return redirect('mi_perfil')

        # Email único (si lo cambió, que no choque con otro cliente)
        if email and email != (cliente.email or ''):
            if Cliente.objects.filter(email=email).exclude(pk=cliente.pk).exists():
                messages.error(request, "Ese correo ya está registrado por otra cuenta.")
                return redirect('mi_perfil')

        request.user.first_name = nombre
        request.user.last_name = apellido
        if email:
            request.user.email = email
        request.user.save()

        cliente.nombre = f"{nombre} {apellido}".strip()
        cliente.email = email or cliente.email
        cliente.telefono = telefono
        cliente.direccion_facturacion = direccion
        cliente.save()

        messages.success(request, "✅ Tus datos fueron actualizados correctamente.")
        return redirect('mi_perfil')

    return render(request, 'perfil.html', {
        'cliente': cliente,
        'usuario': request.user,
    })


# ── 13. SOPORTE / CONTACTO ───────────────────────────────────────────────────
def soporte(request):
    """Página de ayuda con preguntas frecuentes y formulario de contacto.
    El formulario envía un correo al buzón de soporte de la librería."""
    if request.method == 'POST':
        from django.core.mail import EmailMessage

        nombre = request.POST.get('nombre', '').strip()
        email = request.POST.get('email', '').strip()
        asunto = request.POST.get('asunto', '').strip() or "Consulta desde el sitio"
        mensaje = request.POST.get('mensaje', '').strip()

        if not nombre or not email or not mensaje:
            messages.error(request, "Completa tu nombre, correo y mensaje.")
            return redirect('soporte')

        cuerpo = (
            f"Nuevo mensaje de soporte desde el sitio web:\n\n"
            f"Nombre: {nombre}\n"
            f"Correo: {email}\n"
            f"Asunto: {asunto}\n\n"
            f"Mensaje:\n{mensaje}\n"
        )
        try:
            correo = EmailMessage(
                subject=f"[Soporte] {asunto}",
                body=cuerpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.SOPORTE_EMAIL],
                reply_to=[email],  # al responder, le llega al cliente
            )
            correo.send(fail_silently=True)

            # Acuse de recibo al cliente
            from django.core.mail import send_mail
            send_mail(
                subject="Recibimos tu mensaje — Librería Chichi",
                message=(
                    f"Hola {nombre},\n\n"
                    f"¡Gracias por escribirnos! Recibimos tu mensaje y te responderemos pronto.\n\n"
                    f"Tu consulta:\n\"{mensaje}\"\n\n"
                    f"Un saludo,\nEquipo Librería Chichi"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"⚠️ No se pudo enviar el correo de soporte: {e}")

        messages.success(request, "✅ ¡Mensaje enviado! Te responderemos a tu correo lo antes posible.")
        return redirect('soporte')

    return render(request, 'soporte.html', {
        'tienda': {
            'email': getattr(settings, 'TIENDA_EMAIL', ''),
            'telefono': getattr(settings, 'TIENDA_TELEFONO', ''),
            'direccion': getattr(settings, 'TIENDA_DIRECCION', ''),
            'horario': getattr(settings, 'TIENDA_HORARIO', ''),
        },
    })


# ── 14. REPORTES DE VENTAS (descargar / enviar por correo) ───────────────────
def descargar_reporte(request):
    """Descarga el Excel de ventas de una semana.
    ?fecha=YYYY-MM-DD elige la semana (cualquier día de esa semana); sin
    parámetro, usa la semana actual."""
    if not permisos.puede_ver_reportes(request.user):
        messages.error(request, "No tienes permiso para ver los reportes.")
        return redirect('inicio' if not permisos.es_backoffice(request.user) else 'panel_admin')

    from datetime import datetime
    fecha = None
    fstr = request.GET.get('fecha', '').strip()
    if fstr:
        try:
            fecha = datetime.strptime(fstr, '%Y-%m-%d').date()
        except ValueError:
            fecha = None

    from .reportes import generar_excel
    nombre, contenido = generar_excel(fecha)
    if contenido is None:
        messages.error(request, "Falta la librería 'openpyxl' para generar el Excel.")
        return redirect('panel_ventas')

    from django.http import HttpResponse
    resp = HttpResponse(
        contenido,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    resp['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return resp


def enviar_reporte(request):
    """Envía el reporte de ventas por correo al buzón configurado (REPORTE_EMAIL).

    Se puede gatillar de dos formas:
      • Un administrador con permiso de reportes (botón del panel).
      • Un servicio programador externo, con ?token=<REPORTE_TOKEN> en la URL
        (así se logra el envío automático semanal).
    ?fecha=YYYY-MM-DD elige la semana; sin parámetro, la semana actual."""
    token = request.GET.get('token', '')
    token_ok = bool(getattr(settings, 'REPORTE_TOKEN', '')) and token == settings.REPORTE_TOKEN

    if not token_ok and not permisos.puede_ver_reportes(request.user):
        messages.error(request, "No tienes permiso para enviar reportes.")
        return redirect('inicio' if not permisos.es_backoffice(request.user) else 'panel_admin')

    from datetime import datetime
    fecha = None
    fstr = request.GET.get('fecha', '').strip()
    if fstr:
        try:
            fecha = datetime.strptime(fstr, '%Y-%m-%d').date()
        except ValueError:
            fecha = None

    destino = getattr(settings, 'REPORTE_EMAIL', '') or getattr(settings, 'DEFAULT_FROM_EMAIL', '')
    from .reportes import enviar_reporte_correo
    ok = enviar_reporte_correo(destino, fecha)

    # Si vino del programador externo (token), responder JSON sin redirigir.
    if token_ok:
        from django.http import JsonResponse
        return JsonResponse({'ok': bool(ok), 'destinatario': destino})

    if ok:
        messages.success(request, f"📧 Reporte enviado a {destino}.")
    else:
        messages.error(request, "No se pudo enviar el reporte. Revisa la configuración de correo.")
    return redirect('panel_ventas')
