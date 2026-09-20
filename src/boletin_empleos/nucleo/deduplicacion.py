"""Deduplicación entre fuentes. Lógica pura.

La misma vacante suele publicarse en varias bolsas. Se conserva la de la
fuente más confiable. Deduplicar NO es descartar: la oferta sí entra al
boletín, una sola vez (spec §8.6).
"""

from boletin_empleos.modelos import Oferta
from boletin_empleos.nucleo.relevancia import normalizar_texto


def clave_dedup(oferta: Oferta) -> str:
    """Clave estable e independiente de la fuente."""
    empresa = normalizar_texto(oferta.empresa or "")
    titulo = normalizar_texto(oferta.titulo)
    ubicacion = normalizar_texto(oferta.ubicacion or "")
    return f"{empresa}|{titulo}|{ubicacion}"


def deduplicar(
    ofertas: list[Oferta], confianza_por_fuente: dict[str, float]
) -> tuple[list[Oferta], list[Oferta]]:
    """Devuelve (únicas, duplicadas). Gana la oferta de la fuente más confiable."""
    mejor: dict[str, Oferta] = {}
    duplicadas: list[Oferta] = []

    for oferta in ofertas:
        clave = clave_dedup(oferta)
        actual = mejor.get(clave)
        if actual is None:
            mejor[clave] = oferta
            continue
        if confianza_por_fuente.get(oferta.fuente, 0.0) > confianza_por_fuente.get(
            actual.fuente, 0.0
        ):
            mejor[clave] = oferta
            duplicadas.append(actual)
        else:
            duplicadas.append(oferta)

    return (list(mejor.values()), duplicadas)
