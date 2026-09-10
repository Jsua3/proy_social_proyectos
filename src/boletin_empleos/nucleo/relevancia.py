"""Puntuación de relevancia. Lógica pura: sin red, sin disco."""

import re
import unicodedata
from functools import lru_cache

from boletin_empleos.config import Vocabulario
from boletin_empleos.modelos import Oferta

_PESO_TITULO = 0.7
_PESO_DESCRIPCION = 0.3


def normalizar_texto(texto: str) -> str:
    """Minúscula y sin tildes, para comparar de forma estable en español."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return " ".join(sin_tildes.lower().split())


@lru_cache(maxsize=512)
def patron_de(termino: str) -> re.Pattern[str]:
    """Compila un término del vocabulario exigiendo frontera de palabra.

    Buscar por subcadena rompe el filtro: `ios` casa dentro de *negocios*,
    *servicios*, *estudios*, *medios*, *precios* y *oficios* — todas comunísimas
    en títulos de ofertas colombianas. Medido sobre 50 ofertas reales del SPE, la
    única que pasaba el filtro era "Jardinero y Oficios Varios".

    La frontera se exige **solo donde el borde del término es alfanumérico**, para
    que `.net` siga casando dentro de `asp.net` y `c#` siga funcionando.
    """
    inicio = r"(?<![a-z0-9])" if termino[:1].isalnum() else ""
    fin = r"(?![a-z0-9])" if termino[-1:].isalnum() else ""
    return re.compile(inicio + re.escape(termino) + fin)


def contiene(texto: str, termino: str) -> bool:
    """¿Aparece `termino` en `texto` como palabra, no como fragmento?"""
    return patron_de(normalizar_texto(termino)).search(texto) is not None


def puntuar_relevancia(oferta: Oferta, vocabulario: Vocabulario) -> float:
    """Devuelve 0.0–1.0. Un término excluido anula la oferta por completo."""
    titulo = normalizar_texto(oferta.titulo)
    descripcion = normalizar_texto(oferta.descripcion)
    completo = f"{titulo} {descripcion}"

    if any(contiene(completo, e) for e in vocabulario.excluidos):
        return 0.0

    terminos = vocabulario.cargos + vocabulario.tecnologias
    if not terminos:
        return 0.0

    en_titulo = sum(1 for t in terminos if contiene(titulo, t))
    en_descripcion = sum(1 for t in terminos if contiene(descripcion, t))

    puntaje = _PESO_TITULO * _saturar(en_titulo) + _PESO_DESCRIPCION * _saturar(en_descripcion)
    return round(min(puntaje, 1.0), 4)


def _saturar(coincidencias: int) -> float:
    """1 coincidencia ya vale mucho; más coincidencias suman con rendimiento decreciente."""
    if coincidencias <= 0:
        return 0.0
    return min(1.0, 0.6 + 0.2 * (coincidencias - 1))
