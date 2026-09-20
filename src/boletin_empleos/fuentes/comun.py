# src/boletin_empleos/fuentes/comun.py
"""Utilidades compartidas por los adaptadores de fuente.

Existe para que la misma lógica no viva copiada en cada adaptador: las cuatro
fuentes entregan fechas en variantes de ISO 8601 y todas necesitan interpretarlas
igual. Lo mismo pasa con el mojibake del SPE y los códigos internos que algunas
bolsas pegan al final del título — no son un problema de una sola fuente.
"""

import re
from datetime import date, datetime


def fecha_iso(valor: str | None) -> date | None:
    """Interpreta una fecha ISO 8601, con o sin sufijo `Z`. None si no se puede."""
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).date()
    except ValueError:
        return None


# Cualquier tramo de caracteres no ASCII es candidato a mojibake: el SPE entrega
# texto UTF-8 que alguien en su cadena decodificó como cp1252 antes de guardarlo
# (evidencia real: `QuindÃ­o`, `FormaciÃ³n`, `Lider tÃ©cnico/a QA` en
# tests/fixtures/spe_pagina.json y en el primer boletín real — spec ronda 2, R2-1).
_TRAMO_NO_ASCII = re.compile(r"[^\x00-\x7f]+")


def reparar_texto(texto: str | None) -> str | None:
    """Repara mojibake (UTF-8 leído como cp1252) segmento por segmento.

    Solo se toca cada tramo de caracteres no ASCII, y solo si reinterpretarlo
    como cp1252 y volver a decodificarlo como UTF-8 tiene éxito. Esa condición
    es lo que aísla el mojibake real del texto que ya está bien: una letra
    acentuada aislada y correcta (p. ej. la í de "Medellín") no es, por sí
    sola, una secuencia UTF-8 válida, así que el intento de reparación falla y
    el tramo se deja intacto. Lo mismo protege los bytes ya irrecuperables
    (U+FFFD, que ni siquiera se puede codificar en cp1252) y los emojis o
    signos fuera de cp1252. Nunca lanza: ante cualquier entrada rara devuelve
    el texto sin tocar.
    """
    if not texto:
        return texto

    def _reparar_tramo(coincidencia: re.Match[str]) -> str:
        tramo = coincidencia.group(0)
        try:
            return tramo.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return tramo

    try:
        return _TRAMO_NO_ASCII.sub(_reparar_tramo, texto)
    except Exception:  # defensa adicional: un adaptador nunca lanza.
        return texto


# Algunas bolsas pegan su propio código de control al final del título público,
# con la forma <al menos 5 dígitos>-<dígitos>, separado del texto real por un
# espacio (evidencia real: "Desarrollador/a Java/PHP 1626256994-142" — spec
# ronda 2, R2-5). Un solo grupo de dígitos tras un guion con espacios alrededor
# ("Auxiliar ... Temporal - 147130") no es este patrón y se deja igual.
_CODIGO_INTERNO_FINAL = re.compile(r"\s+\d{5,}-\d+\s*$")


def limpiar_titulo(titulo: str | None) -> str | None:
    """Quita un código interno final del título, si lo tiene. Nunca lanza."""
    if not titulo:
        return titulo
    try:
        return _CODIGO_INTERNO_FINAL.sub("", titulo)
    except Exception:  # defensa adicional: un adaptador nunca lanza.
        return titulo
