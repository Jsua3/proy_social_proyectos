"""Prioridad geográfica: el eje cafetero primero.

La Coordinación está en Armenia. Un egresado ve antes una vacante de Pereira que
una de Medellín, aunque la de Medellín puntúe más alto en pertinencia.
"""

import pytest

from boletin_empleos.config import ConfigGeografia
from boletin_empleos.nucleo.geografia import es_del_eje_cafetero

GEO = ConfigGeografia(
    departamentos=["quindio", "risaralda", "caldas"],
    municipios=["armenia", "pereira", "manizales", "dosquebradas", "santa rosa de cabal"],
    otros_departamentos=["antioquia", "cordoba", "cundinamarca", "valle del cauca", "bogota"],
)


@pytest.mark.parametrize(
    "ubicacion, esperado",
    [
        # El departamento manda cuando está nombrado.
        ("ARMENIA, QUINDIO", True),
        ("Pereira, Risaralda", True),
        ("MANIZALES, CALDAS", True),
        ("DEPARTAMENTO QUINDIO", True),
        # Sin departamento, decide el municipio.
        ("Armenia", True),
        ("Dosquebradas", True),
        ("Santa Rosa de Cabal", True),
        # Colisiones reales: Antioquia también tiene un Armenia y un Caldas.
        ("Armenia, Antioquia", False),
        ("CALDAS, ANTIOQUIA", False),
        # Y al revés: Córdoba es municipio del Quindío además de departamento.
        # El SPE escribe el departamento de último, y ese es el que manda.
        ("CORDOBA, QUI, QUINDIO", True),
        ("RIOSUCIO, CAL, CALDAS", True),
        # Resto del país.
        ("MEDELLÍN, ANTIOQUIA", False),
        ("BOGOTÁ, D.C., BOGOTÁ, D.C.", False),
        ("Cali, Valle del Cauca", False),
        ("Remoto", False),
        ("", False),
        (None, False),
    ],
)
def test_reconoce_el_eje_cafetero(ubicacion, esperado):
    assert es_del_eje_cafetero(ubicacion, GEO) is esperado


def test_sin_vocabulario_geografico_nada_es_prioritario():
    """Quien no quiera prioridad geográfica vacía las listas de config.toml."""
    assert es_del_eje_cafetero("ARMENIA, QUINDIO", ConfigGeografia()) is False
