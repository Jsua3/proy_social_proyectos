# src/boletin_empleos/enriquecimiento/nulo.py
"""Implementación por defecto: sin LLM. El boletín sale igual, más escueto."""

from boletin_empleos.modelos import Evaluacion

_EDITORIAL_FIJA = (
    "A continuación encontrará las vacantes de desarrollo de software publicadas "
    "durante las últimas dos semanas en fuentes verificadas, filtradas por "
    "pertinencia para egresados del programa."
)


class EnriquecedorNulo:
    def resumir(self, evaluaciones: list[Evaluacion]) -> dict[str, str]:
        return {}

    def editorial(self, evaluaciones: list[Evaluacion], conteos: dict[str, int]) -> str:
        return _EDITORIAL_FIJA
