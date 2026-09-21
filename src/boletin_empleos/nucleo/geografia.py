"""¿La vacante es del eje cafetero? Lógica pura; el vocabulario vive en config.toml.

La Coordinación está en Armenia y sus egresados buscan primero en el Quindío,
Risaralda y Caldas. Esto NO filtra: solo decide qué va de primero.

Los nombres chocan en los dos sentidos: Antioquia tiene un municipio llamado
Armenia y otro llamado Caldas, y el Quindío tiene un municipio llamado Córdoba,
que también es un departamento. Por eso no basta con buscar palabras sueltas:
**manda el último departamento nombrado**, porque el SPE escribe la ubicación
como "MUNICIPIO, DEPARTAMENTO" (verificado: "CORDOBA, QUI, QUINDIO",
"RIOSUCIO, CAL, CALDAS"). Si no se nombra ningún departamento, decide el
municipio.
"""

from boletin_empleos.config import ConfigGeografia
from boletin_empleos.nucleo.relevancia import contiene, normalizar_texto


def es_del_eje_cafetero(ubicacion: str | None, geo: ConfigGeografia) -> bool:
    if not ubicacion:
        return False

    partes = [normalizar_texto(parte) for parte in ubicacion.split(",")]

    del_eje: bool | None = None
    for parte in partes:
        if _menciona(parte, geo.departamentos):
            del_eje = True
        elif _menciona(parte, geo.otros_departamentos):
            del_eje = False

    if del_eje is not None:
        return del_eje
    return any(_menciona(parte, geo.municipios) for parte in partes)


def _menciona(parte: str, terminos: list[str]) -> bool:
    # Sin flexión: los topónimos no se pluralizan, y "caldas" ya termina en ese.
    return any(contiene(parte, termino, permitir_flexion=False) for termino in terminos)
