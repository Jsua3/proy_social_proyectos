# src/boletin_empleos/enriquecimiento/nulo.py
"""Implementación por defecto: sin LLM. El boletín sale igual, más escueto."""

from boletin_empleos.modelos import Evaluacion

# R2-6: el texto anterior decía "publicadas durante las últimas dos semanas",
# pero eso es falso — la regla de vigencia (nucleo/vigencia.py) deja entrar
# ofertas publicadas mucho antes mientras no hayan vencido según su propia
# fecha de vencimiento. El texto ya no afirma una ventana de tiempo que el
# filtro no respeta.
_EDITORIAL_FIJA = (
    "A continuación encontrará vacantes de desarrollo de software vigentes a la "
    "fecha, recogidas en fuentes verificadas y filtradas por pertinencia para "
    "egresados del programa."
)


class EnriquecedorNulo:
    def resumir(self, evaluaciones: list[Evaluacion]) -> dict[str, str]:
        return {}

    def editorial(self, evaluaciones: list[Evaluacion], conteos: dict[str, int]) -> str:
        return _EDITORIAL_FIJA
