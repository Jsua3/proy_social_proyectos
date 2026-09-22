# src/boletin_empleos/enriquecimiento/nulo.py
"""Implementación por defecto: sin LLM. El boletín sale igual, más escueto."""

from boletin_empleos.modelos import Evaluacion


class EnriquecedorNulo:
    """El texto fijo. Nombra la carrera, porque el mismo código sirve a varias.

    R2-6: el texto anterior decía "publicadas durante las últimas dos semanas",
    pero eso es falso — la regla de vigencia (nucleo/vigencia.py) deja entrar
    ofertas publicadas mucho antes mientras no hayan vencido según su propia
    fecha de vencimiento. El texto no afirma una ventana de tiempo que el filtro
    no respeta.
    """

    def __init__(self, programa: str = "") -> None:
        self._programa = programa

    def resumir(self, evaluaciones: list[Evaluacion]) -> dict[str, str]:
        return {}

    def editorial(self, evaluaciones: list[Evaluacion], conteos: dict[str, int]) -> str:
        para_quien = (
            f"para los egresados de {self._programa}"
            if self._programa
            else "para egresados del programa"
        )
        return (
            "A continuación encontrará vacantes vigentes a la fecha, recogidas en fuentes "
            f"verificadas y filtradas por pertinencia {para_quien}."
        )
