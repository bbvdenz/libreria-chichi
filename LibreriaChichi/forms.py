from django import forms
from django.contrib.auth.models import User
from .models import Cliente
import re

REGIONES_CHILE = [
    ('', 'Seleccione Región...'),
    ('Tarapacá', 'Región de Tarapacá'),
    ('Antofagasta', 'Región de Antofagasta'),
    ('Atacama', 'Región de Atacama'),
    ('Coquimbo', 'Región de Coquimbo'),
    ('Valparaíso', 'Región de Valparaíso'),
    ('Metropolitana', 'Región Metropolitana de Santiago'),
    ("O'Higgins", "Región del Libertador Gral. Bernardo O'Higgins"),
    ('Maule', 'Región del Maule'),
    ('Ñuble', 'Región de Ñuble'),
    ('Biobío', 'Región del Biobío'),
    ('Araucanía', 'Región de la Araucanía'),
    ('Los Ríos', 'Región de Los Ríos'),
    ('Los Lagos', 'Región de Los Lagos'),
    ('Aysén', 'Región Aysén del Gral. Carlos Ibáñez del Campo'),
    ('Magallanes', 'Región de Magallanes y de la Antártica Chilena'),
]

COMUNAS_CHILE = [('', 'Seleccione una región primero...')]


class RegistroClienteForm(forms.Form):
    rut = forms.CharField(max_length=12, required=True, label="RUT")
    nombre = forms.CharField(max_length=50, required=True, label="Nombre")
    apellido = forms.CharField(max_length=50, required=True, label="Apellido")
    email = forms.EmailField(required=True, label="Correo Electrónico")
    telefono = forms.CharField(max_length=15, required=False, label="Teléfono")
    direccion_calle = forms.CharField(max_length=150, required=True, label="Calle y Número")
    region = forms.ChoiceField(choices=REGIONES_CHILE, required=True, label="Región")
    comuna = forms.CharField(max_length=100, required=True, label="Comuna")
    password = forms.CharField(widget=forms.PasswordInput, required=True, label="Contraseña")
    password_confirm = forms.CharField(widget=forms.PasswordInput, required=True, label="Confirmar Contraseña")

    def clean_rut(self):
        rut_ingresado = self.cleaned_data.get('rut', '').strip()
        if not rut_ingresado:
            raise forms.ValidationError("El RUT es obligatorio.")

        rut_limpio = rut_ingresado.replace('.', '').replace('-', '').upper()

        if len(rut_limpio) < 2:
            raise forms.ValidationError("El RUT es demasiado corto.")

        cuerpo = rut_limpio[:-1]
        dv_ingresado = rut_limpio[-1]

        if not cuerpo.isdigit():
            raise forms.ValidationError("El cuerpo del RUT debe contener solo números.")

        if len(cuerpo) < 7 or len(cuerpo) > 8:
            raise forms.ValidationError("El RUT debe tener entre 7 y 8 dígitos.")

        # Algoritmo módulo 11
        suma = 0
        multiplo = 2
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

        if dv_ingresado != dv_esperado:
            raise forms.ValidationError(
                f"RUT inválido. El dígito verificador correcto para {cuerpo} es '{dv_esperado}', no '{dv_ingresado}'."
            )

        rut_formateado = f"{cuerpo}-{dv_ingresado}"

        if Cliente.objects.filter(rut=rut_formateado).exists():
            raise forms.ValidationError("Este RUT ya está registrado.")
        if User.objects.filter(username=rut_formateado).exists():
            raise forms.ValidationError("Este RUT ya tiene una cuenta asociada.")

        return rut_formateado

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()

        if not email:
            raise forms.ValidationError("El correo electrónico es obligatorio.")

        patron = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
        if not re.match(patron, email):
            raise forms.ValidationError("Ingresa un correo electrónico válido. Ej: nombre@gmail.com")

        partes = email.split('@')
        if len(partes) != 2 or '.' not in partes[1]:
            raise forms.ValidationError("El dominio del correo no es válido.")

        # Solo bloquear si ya existe un USUARIO registrado con ese email
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este correo ya tiene una cuenta registrada. Inicia sesión.")

        # Solo bloquear cliente si tiene usuario asociado (no si fue invitado)
        cliente_existente = Cliente.objects.filter(email=email).first()
        if cliente_existente and cliente_existente.usuario is not None:
            raise forms.ValidationError("Este correo ya está en uso.")

        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "Las contraseñas no coinciden.")
        return cleaned_data