from django.contrib import admin
from .models import Cliente, Producto, Stock, Pedido, DetallePedido, Entrega, Pago
from .models import Transferencia, ClaveAPI

class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 1  

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id_pedido', 'id_cliente', 'fecha_pedido', 'estado_pedido', 'tipo_pedido')
    list_filter = ('estado_pedido', 'tipo_pedido')
    inlines = [DetallePedidoInline]  

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('id_producto', 'nombre_producto', 'precio')
    search_fields = ('nombre_producto',)

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('id_cliente', 'nombre', 'telefono', 'email')
    search_fields = ('nombre', 'email')

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('id_stock', 'id_producto', 'cantidad_disponible', 'fecha_actualizacion')

admin.site.register(Entrega)
admin.site.register(Pago)


@admin.register(Transferencia)
class TransferenciaAdmin(admin.ModelAdmin):
    list_display = ('id_transferencia', 'id_pedido', 'banco', 'numero_operacion',
                    'monto', 'coincide_monto', 'estado', 'creado')
    list_filter = ('estado', 'coincide_monto', 'banco')
    search_fields = ('numero_operacion', 'rut_pagador')
    readonly_fields = ('creado', 'validado_en', 'validado_por')


@admin.register(ClaveAPI)
class ClaveAPIAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'clave', 'activa', 'creada')
    list_filter = ('activa',)