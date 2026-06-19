from django.db import models
from django.contrib.auth.models import User  # <-- Importante para enlazar el Login de Django

class Cliente(models.Model):
    id_cliente = models.AutoField(primary_key=True)
    
    # Enlazamos al usuario de Django (es nulo si la persona compra como "Invitado")
    usuario = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='usuario_id')
    
    # Nuevos campos obligatorios para el registro
    rut = models.CharField(max_length=12, unique=True, null=True, blank=True)
    direccion_facturacion = models.TextField(null=True, blank=True)
    
    # Campos que ya tenías
    nombre = models.TextField()
    telefono = models.TextField(blank=True, null=True)
    email = models.TextField(unique=True, blank=True, null=True)

    class Meta:
        db_table = 'cliente'

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    id_producto = models.AutoField(primary_key=True)
    # SKU = código único de identificación del producto (ej: LAP-HB-001).
    # Permite buscar productos y, sobre todo, saber si un producto que llega
    # ya existe para actualizarlo (promedio ponderado) en vez de duplicarlo.
    sku = models.CharField(max_length=40, unique=True, null=True, blank=True)
    nombre_producto = models.TextField()
    precio = models.DecimalField(max_length=10, decimal_places=2, max_digits=10)
    categoria = models.CharField(max_length=100, default='General')
    imagen = models.ImageField(upload_to='productos/', null=True, blank=True)

    class Meta:
        db_table = 'producto'

    def __str__(self):
        return self.nombre_producto


class Stock(models.Model):
    id_stock = models.AutoField(primary_key=True)
    cantidad_disponible = models.IntegerField(default=0)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    id_producto = models.OneToOneField(Producto, on_delete=models.CASCADE, db_column='id_producto')

    class Meta:
        db_table = 'stock'

    def __str__(self):
        return f"Stock de {self.id_producto.nombre_producto}: {self.cantidad_disponible}"


class Pedido(models.Model):
    id_pedido = models.AutoField(primary_key=True)
    fecha_pedido = models.DateField(auto_now_add=True)
    estado_pedido = models.TextField(default='pendiente')
    fecha_entrega_acordada = models.DateField(blank=True, null=True)
    tipo_pedido = models.TextField()
    id_cliente = models.ForeignKey(Cliente, on_delete=models.RESTRICT, db_column='id_cliente')

    class Meta:
        db_table = 'pedido'

    def __str__(self):
        return f"Pedido #{self.id_pedido} - {self.id_cliente.nombre}"


class DetallePedido(models.Model):
    id_detalle = models.AutoField(primary_key=True)
    cantidad = models.IntegerField()
    precio_unitario = models.DecimalField(max_length=10, decimal_places=2, max_digits=10)
    id_pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, db_column='id_pedido')
    id_producto = models.ForeignKey(Producto, on_delete=models.RESTRICT, db_column='id_producto')

    class Meta:
        db_table = 'detallepedido'

    def __str__(self):
        return f"{self.cantidad}x {self.id_producto.nombre_producto} (Pedido #{self.id_pedido.id_pedido})"


class Entrega(models.Model):
    id_entrega = models.AutoField(primary_key=True)
    fecha_entrega = models.DateField()
    presencial = models.BooleanField(default=True)
    estado_entrega = models.TextField(default='pendiente')
    id_pedido = models.OneToOneField(Pedido, on_delete=models.CASCADE, db_column='id_pedido')

    class Meta:
        db_table = 'entrega'


class Pago(models.Model):
    id_pago = models.AutoField(primary_key=True)
    fecha_pago = models.DateField(auto_now_add=True)
    monto = models.DecimalField(max_length=10, decimal_places=2, max_digits=10)
    metodo_pago = models.TextField()
    estado_pago = models.TextField(default='pendiente')
    id_entrega = models.OneToOneField(Entrega, on_delete=models.SET_NULL, blank=True, null=True, db_column='id_entrega')

    class Meta:
        db_table = 'pago'


# ════════════════════════════════════════════════════════════════════════════
#  TRANSFERENCIAS BANCARIAS  (para la API de validación)
# ════════════════════════════════════════════════════════════════════════════
class Transferencia(models.Model):
    """Comprobante de una transferencia bancaria informada por el cliente.

    Queda en estado 'pendiente' hasta que un administrador o cajero la
    valide (aprobar/rechazar) desde el panel o por la API.
    """
    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_VALIDADA = 'validada'
    ESTADO_RECHAZADA = 'rechazada'
    ESTADOS = [
        (ESTADO_PENDIENTE, 'Pendiente de validación'),
        (ESTADO_VALIDADA, 'Validada'),
        (ESTADO_RECHAZADA, 'Rechazada'),
    ]

    id_transferencia = models.AutoField(primary_key=True)
    id_pedido = models.ForeignKey(
        Pedido, on_delete=models.CASCADE, db_column='id_pedido',
        related_name='transferencias',
    )
    id_pago = models.OneToOneField(
        Pago, on_delete=models.SET_NULL, null=True, blank=True,
        db_column='id_pago',
    )
    # Datos que informa el cliente
    banco = models.CharField(max_length=80)
    numero_operacion = models.CharField(max_length=60)
    rut_pagador = models.CharField(max_length=12)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_transferencia = models.DateField()
    email_contacto = models.EmailField(blank=True, null=True)
    comprobante = models.ImageField(upload_to='transferencias/', null=True, blank=True)

    # Resultado de la validación
    estado = models.CharField(max_length=12, choices=ESTADOS, default=ESTADO_PENDIENTE)
    coincide_monto = models.BooleanField(default=False)
    motivo_rechazo = models.TextField(blank=True, null=True)
    validado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transferencias_validadas',
    )
    validado_en = models.DateTimeField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'transferencia'
        ordering = ['-creado']
        # No se puede repetir el mismo comprobante en el mismo banco
        unique_together = [('banco', 'numero_operacion')]
        permissions = [
            ('validar_transferencia', 'Puede validar transferencias bancarias'),
        ]

    def __str__(self):
        return f"Transf. {self.banco} #{self.numero_operacion} ({self.estado})"

    def como_dict(self):
        """Representación JSON-serializable (para la API)."""
        return {
            'id': self.id_transferencia,
            'pedido_id': self.id_pedido_id,
            'pago_id': self.id_pago_id,
            'banco': self.banco,
            'numero_operacion': self.numero_operacion,
            'rut_pagador': self.rut_pagador,
            'monto': float(self.monto),
            'fecha_transferencia': self.fecha_transferencia.isoformat() if self.fecha_transferencia else None,
            'email_contacto': self.email_contacto,
            'estado': self.estado,
            'coincide_monto': self.coincide_monto,
            'motivo_rechazo': self.motivo_rechazo,
            'validado_por': self.validado_por.username if self.validado_por else None,
            'validado_en': self.validado_en.isoformat() if self.validado_en else None,
            'creado': self.creado.isoformat() if self.creado else None,
        }


class ClaveAPI(models.Model):
    """Llave de acceso para integraciones externas que usan la API
    (por ejemplo, un script de conciliación bancaria)."""
    nombre = models.CharField(max_length=100)
    clave = models.CharField(max_length=64, unique=True, db_index=True)
    activa = models.BooleanField(default=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'clave_api'
        verbose_name = 'Clave API'
        verbose_name_plural = 'Claves API'

    def __str__(self):
        estado = 'activa' if self.activa else 'inactiva'
        return f"{self.nombre} ({estado})"