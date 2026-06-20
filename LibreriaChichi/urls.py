from django.urls import path
from . import views
from . import api

urlpatterns = [
    path('', views.inicio_base, name='inicio'),
    path('catalogo/', views.catalogo_publico, name='catalogo'),
    path('agregar/<int:producto_id>/', views.agregar_al_carrito, name='agregar_al_carrito'),
    path('carrito/', views.ver_carrito, name='ver_carrito'),
    path('carrito/modificar/<int:producto_id>/<str:accion>/', views.modificar_carrito, name='modificar_carrito'),
    path('pago/', views.procesar_pago, name='procesar_pago'),
    path('registro/', views.registro_usuario, name='registro'),
    path('login/', views.iniciar_sesion, name='login'),
    path('login-admin/', views.iniciar_sesion_admin, name='login_admin'),  # ← NUEVA
    path('logout/', views.cerrar_sesion, name='logout'),
    path('recuperar-password/', views.recuperar_password, name='recuperar_password'),
    path('recuperar-password/confirmar/<uidb64>/<token>/', views.confirmar_nueva_password, name='confirmar_nueva_password'),
    path('mi-perfil/', views.mi_perfil, name='mi_perfil'),
    path('soporte/', views.soporte, name='soporte'),
    path('gestion/', views.panel_admin, name='panel_admin'),
    path('gestion/producto/agregar/', views.admin_agregar_producto, name='admin_agregar_producto'),
    path('gestion/producto/actualizar/', views.admin_actualizar_producto, name='admin_actualizar_producto'),
    path('gestion/producto/editar/<int:producto_id>/', views.admin_editar_producto, name='admin_editar_producto'),
    path('gestion/producto/eliminar/<int:producto_id>/', views.admin_eliminar_producto, name='admin_eliminar_producto'),
    path('gestion/crear-admin/', views.admin_crear_subadmin, name='admin_crear_subadmin'),
    path('gestion/admin/<int:user_id>/editar/', views.admin_editar_subadmin, name='admin_editar_subadmin'),
    path('gestion/admin/<int:user_id>/eliminar/', views.admin_eliminar_subadmin, name='admin_eliminar_subadmin'),
    path('gestion/pedidos/', views.panel_pedidos, name='panel_pedidos'),
    path('gestion/pedido/<int:pedido_id>/estado/', views.cambiar_estado_pedido, name='cambiar_estado_pedido'),
    path('gestion/pedido/<int:pedido_id>/boleta/', views.generar_boleta, name='generar_boleta'),
    path('gestion/ventas/', views.panel_ventas, name='panel_ventas'),
    path('gestion/pos/', views.panel_pos, name='panel_pos'),
    path('gestion/pos/registrar/', views.registrar_venta_pos, name='registrar_venta_pos'),
    # Panel de transferencias (staff)
    path('gestion/transferencias/', views.panel_transferencias, name='panel_transferencias'),

    # ── API v1: validación de transferencias ──────────────────────────────
    path('api/v1/ping/', api.ping, name='api_ping'),
    path('api/v1/transferencias/registrar/', api.registrar_transferencia, name='api_registrar_transferencia'),
    path('api/v1/transferencias/', api.listar_transferencias, name='api_listar_transferencias'),
    path('api/v1/transferencias/<int:transferencia_id>/', api.detalle_transferencia, name='api_detalle_transferencia'),
    path('api/v1/transferencias/<int:transferencia_id>/validar/', api.validar_transferencia, name='api_validar_transferencia'),
]