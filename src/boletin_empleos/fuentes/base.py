# src/boletin_empleos/fuentes/base.py
"""Puerto de entrada: contrato que toda fuente de empleo debe cumplir.

`base_permiso`, `atribucion` y `url_atribucion` son obligatorios por diseño:
una fuente que no puede declarar por qué tenemos derecho a usarla no tiene
dónde encajar en este sistema (spec §4).
"""

from typing import Protocol, runtime_checkable

from boletin_empleos.modelos import Oferta


@runtime_checkable
class FuenteEmpleo(Protocol):
    nombre: str
    base_permiso: str
    atribucion: str
    url_atribucion: str
    confianza_base: float

    def obtener(self) -> list[Oferta]:
        """Devuelve ofertas normalizadas. Ante fallo, lista vacía — nunca excepción."""
        ...
