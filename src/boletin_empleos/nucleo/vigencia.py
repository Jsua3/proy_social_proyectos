"""Filtro de vigencia. Crítico por la periodicidad quincenal. Lógica pura."""

from datetime import date

from boletin_empleos.modelos import Oferta


def esta_vigente(oferta: Oferta, hoy: date, dias_max: int) -> tuple[bool, str]:
    """La fecha de vencimiento declarada manda sobre la antigüedad estimada.

    Sin ninguna fecha no se castiga la oferta: la verificación del enlace,
    que ocurre después y sí hace red, se encargará de descartarla si murió.
    """
    if oferta.fecha_vencimiento is not None:
        if oferta.fecha_vencimiento < hoy:
            return (False, f"venció el {oferta.fecha_vencimiento.isoformat()}")
        return (True, "")

    # Un portal de empresa baja la vacante cuando la llena: que siga publicada
    # es prueba de que sigue abierta, y su antigüedad no dice lo contrario.
    if oferta.vigencia_verificada:
        return (True, "")

    if oferta.fecha_publicacion is not None:
        antiguedad = (hoy - oferta.fecha_publicacion).days
        if antiguedad > dias_max:
            return (False, f"publicada hace {antiguedad} días (máximo {dias_max})")
        return (True, "")

    return (True, "")
