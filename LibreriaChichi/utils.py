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
