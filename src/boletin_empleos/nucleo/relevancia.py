"""Puntuación de relevancia. Lógica pura: sin red, sin disco."""

import re
import unicodedata
from functools import lru_cache

from boletin_empleos.config import PesosRelevancia, Vocabulario
from boletin_empleos.modelos import Oferta

_SUFIJOS_FLEXION = r"(?:as|es|os|a|s)?"
_LONGITUD_MINIMA_FLEXION = 5

# En español solo se flexionan los SUSTANTIVOS DE AGENTE, y tienen terminaciones
# características. Esto no es una lista de excepciones que haya que auditar: es
# morfología, y por eso se sostiene ante vocabulario nuevo.
#
# Deja fuera automáticamente `docker` (-er), `angular` (-ar), `android` (-id) y
# `tester` (-er), que al flexionarse chocaban con *Dockers* (marca de ropa),
# *angulares* (metalmecánica), *androides* y *testeros* (mueblería). Y deja fuera
# las 32 tecnologías del vocabulario, que son nombres propios.
#
# Un criterio anterior por longitud no bastaba: `docker` tiene 6 caracteres y
# `tester` 6, ambos muy por encima de cualquier umbral razonable.
_TERMINACIONES_DE_AGENTE = (
    "dor",
    "or",
    "ero",
    "era",
    "ario",
    "ente",
    "ante",
    "ista",
    "logo",
    "grafo",
)


def admite_flexion(termino: str) -> bool:
    """¿Es `termino` un sustantivo de agente español, que se flexiona?

    Se mira la última palabra: "ingeniero de datos" no se flexiona al final, pero
    "desarrollador" sí. La longitud mínima protege de terminaciones accidentales.
    """
    ultima = termino.split()[-1] if termino.split() else termino
    return len(ultima) >= _LONGITUD_MINIMA_FLEXION and ultima.endswith(_TERMINACIONES_DE_AGENTE)


def normalizar_texto(texto: str) -> str:
    """Minúscula y sin tildes, para comparar de forma estable en español."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return " ".join(sin_tildes.lower().split())


@lru_cache(maxsize=1024)
def patron_de(termino: str, permitir_flexion: bool = True) -> re.Pattern[str]:
    """Compila un término del vocabulario exigiendo frontera de palabra.

    Buscar por subcadena rompe el filtro: `ios` casa dentro de *negocios*,
    *servicios*, *estudios*, *medios*, *precios* y *oficios* — todas comunísimas
    en títulos de ofertas colombianas. Medido sobre 50 ofertas reales del SPE, la
    única que pasaba el filtro era "Jardinero y Oficios Varios".

    La frontera se exige **solo donde el borde del término es alfanumérico**, para
    que `.net` siga casando dentro de `asp.net` y `c#` siga funcionando.

    A los términos largos que acaban en letra se les permite además un sufijo de
    flexión española, porque las ofertas colombianas se escriben en femenino y en
    plural: sin esto, `desarrollador` no casaría dentro de *Desarrolladora Backend*
    y el filtro descartaría sistemáticamente esas vacantes. Los acrónimos cortos
    quedan fuera de esa concesión para que `sre` no case dentro de *Sres.*

    Quién se flexiona lo decide `admite_flexion`, por morfología: solo los
    sustantivos de agente. El parámetro `permitir_flexion` es la escotilla de
    escape para los pocos casos en que la morfología acierta pero el resultado
    colisiona igual — `conductor` es sustantivo de agente, pero "conductores"
    también son cables. Se alimenta de la lista `sin_flexion` de `config.toml`.
    """
    inicio = r"(?<![a-z0-9])" if termino[:1].isalnum() else ""
    flexion = _SUFIJOS_FLEXION if permitir_flexion and admite_flexion(termino) else ""
    fin = r"(?![a-z0-9])" if termino[-1:].isalnum() else ""
    return re.compile(inicio + re.escape(termino) + flexion + fin)


def contiene(texto_normalizado: str, termino: str, permitir_flexion: bool = True) -> bool:
    """¿Aparece `termino` en `texto_normalizado` como palabra, no como fragmento?

    El primer parámetro se llama así a propósito: **debe venir ya normalizado** con
    `normalizar_texto`, mientras que el término se normaliza aquí. La asimetría es
    deliberada —el texto suele ser una descripción larga que se compara contra
    decenas de términos, y normalizarla en cada comparación sería desperdicio— y el
    nombre la hace evidente en cada punto de llamada. Pasar texto crudo devuelve
    `False` en silencio.
    """
    return (
        patron_de(normalizar_texto(termino), permitir_flexion).search(texto_normalizado) is not None
    )


def puntuar_relevancia(
    oferta: Oferta, vocabulario: Vocabulario, pesos: PesosRelevancia | None = None
) -> float:
    """Devuelve 0.0–1.0. Un término excluido anula la oferta por completo."""
    pesos = pesos or PesosRelevancia()
    titulo = normalizar_texto(oferta.titulo)
    descripcion = normalizar_texto(oferta.descripcion)
    completo = f"{titulo} {descripcion}"

    sin_flexion = {normalizar_texto(s) for s in vocabulario.sin_flexion}

    def flexionable(termino: str) -> bool:
        return normalizar_texto(termino) not in sin_flexion

    if any(contiene(completo, e, flexionable(e)) for e in vocabulario.excluidos):
        return 0.0

    terminos = vocabulario.cargos + vocabulario.tecnologias
    if not terminos:
        return 0.0

    en_titulo = sum(1 for t in terminos if contiene(titulo, t, flexionable(t)))
    en_descripcion = sum(1 for t in terminos if contiene(descripcion, t, flexionable(t)))

    puntaje = pesos.peso_titulo * _saturar(en_titulo, pesos) + pesos.peso_descripcion * _saturar(
        en_descripcion, pesos
    )
    return round(min(puntaje, 1.0), 4)


def _saturar(coincidencias: int, pesos: PesosRelevancia) -> float:
    """1 coincidencia ya vale mucho; más coincidencias suman con rendimiento decreciente."""
    if coincidencias <= 0:
        return 0.0
    return min(1.0, pesos.saturacion_base + pesos.saturacion_incremento * (coincidencias - 1))
