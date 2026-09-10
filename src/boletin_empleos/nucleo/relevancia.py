"""Puntuación de relevancia. Lógica pura: sin red, sin disco."""

import unicodedata

from boletin_empleos.config import Vocabulario
from boletin_empleos.modelos import Oferta

_PESO_TITULO = 0.7
_PESO_DESCRIPCION = 0.3


def normalizar_texto(texto: str) -> str:
    """Minúscula y sin tildes, para comparar de forma estable en español."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return " ".join(sin_tildes.lower().split())


def puntuar_relevancia(oferta: Oferta, vocabulario: Vocabulario) -> float:
    """Devuelve 0.0–1.0. Un término excluido anula la oferta por completo."""
    titulo = normalizar_texto(oferta.titulo)
    descripcion = normalizar_texto(oferta.descripcion)
    completo = f"{titulo} {descripcion}"

    if any(normalizar_texto(e) in completo for e in vocabulario.excluidos):
        return 0.0

    terminos = [normalizar_texto(t) for t in vocabulario.cargos + vocabulario.tecnologias]
    if not terminos:
        return 0.0

    en_titulo = sum(1 for t in terminos if t in titulo)
    en_descripcion = sum(1 for t in terminos if t in descripcion)

    puntaje = _PESO_TITULO * _saturar(en_titulo) + _PESO_DESCRIPCION * _saturar(en_descripcion)
    return round(min(puntaje, 1.0), 4)


def _saturar(coincidencias: int) -> float:
    """1 coincidencia ya vale mucho; más coincidencias suman con rendimiento decreciente."""
    if coincidencias <= 0:
        return 0.0
    return min(1.0, 0.6 + 0.2 * (coincidencias - 1))
