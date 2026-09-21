"""Formatos compartidos por el correo y la web. Sin ellos las dos piezas
escribirían las fechas y los números de maneras distintas."""

from datetime import date

_MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def en_palabras(fecha: date) -> str:
    """«21 de septiembre de 2026». Sin depender de la configuración regional."""
    return f"{fecha.day} de {_MESES[fecha.month - 1]} de {fecha.year}"


def miles(n: int) -> str:
    """9722 -> «9.722», como se escribe en Colombia."""
    return f"{n:,}".replace(",", ".")
