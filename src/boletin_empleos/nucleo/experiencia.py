"""Filtro de nivel de experiencia: junior a semi-senior. Lógica pura."""

from boletin_empleos.config import ConfigExperiencia
from boletin_empleos.modelos import Oferta
from boletin_empleos.nucleo.relevancia import contiene, normalizar_texto


def experiencia_apropiada(
    oferta: Oferta, cfg: ConfigExperiencia, max_meses: int
) -> tuple[bool, str]:
    """Devuelve (apropiado, motivo). El motivo va vacío cuando la oferta pasa.

    El emparejamiento es por frontera de palabra, igual que en relevancia: por
    subcadena, `lead` casaría dentro de *liderar* y `sr.` dentro de otras siglas.
    """
    titulo = normalizar_texto(oferta.titulo)
    for termino in cfg.terminos_excluidos:
        if contiene(titulo, termino):
            return (False, f"el título indica un nivel de experiencia alto: '{termino}'")

    if oferta.meses_experiencia is not None and oferta.meses_experiencia > max_meses:
        return (
            False,
            f"exige {oferta.meses_experiencia} meses de experiencia (máximo {max_meses})",
        )

    return (True, "")
