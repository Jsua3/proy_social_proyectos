# src/boletin_empleos/enriquecimiento/base.py
"""Puerto opcional: prosa generada. Nunca decide qué entra al boletín."""

from typing import Protocol

from boletin_empleos.modelos import Evaluacion


class Enriquecedor(Protocol):
    def resumir(self, evaluaciones: list[Evaluacion]) -> dict[str, str]:
        """Devuelve {id_oferta: resumen de una línea}. Puede devolver {}."""
        ...

    def editorial(self, evaluaciones: list[Evaluacion], conteos: dict[str, int]) -> str:
        """Párrafo de apertura del boletín. Nunca vacío."""
        ...
