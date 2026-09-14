# tests/test_fuente_comun.py
"""Utilidades compartidas por los adaptadores de fuente (`fuentes/comun.py`).

Los literales de mojibake se escriben con escapes \\uXXXX (nunca como bytes
crudos en el archivo) para que el caso de prueba sea exacto y no dependa de
la codificacion de quien edite este archivo despues.
"""

from datetime import date

import pytest

from boletin_empleos.fuentes.comun import fecha_iso, limpiar_titulo, reparar_texto


def test_fecha_iso_interpreta_con_y_sin_sufijo_z():
    assert fecha_iso("2026-09-09T00:00:00.000Z") == date(2026, 9, 9)
    assert fecha_iso("2026-09-09") == date(2026, 9, 9)


def test_fecha_iso_devuelve_none_si_no_se_puede_interpretar():
    assert fecha_iso(None) is None
    assert fecha_iso("") is None
    assert fecha_iso("no es una fecha") is None


# Cada tupla es (entrada con mojibake real, salida esperada ya reparada).
# Evidencia: fixture real del SPE y HTML del primer boletin (ver el brief de
# ronda 2, R2-1). "Ã©" es la representacion UTF-8 de 'e' con tilde
# (bytes C3 A9) mal leida como cp1252 -- byte a byte, no como texto suelto.
CASOS_REPARAR_TEXTO = [
    (
        "Lider tÃ©cnico/a QA",
        "Lider técnico/a QA",
    ),
    (
        "Desarrollador Backend Java â€“ Eventos",
        "Desarrollador Backend Java – Eventos",
    ),
    (
        "EDUCACIÃ“N VIRTUAL",
        "EDUCACIÓN VIRTUAL",
    ),
    (
        "DiseÃ±ador/a junior",
        "Diseñador/a junior",
    ),
    (
        # Ya correcto (i con tilde real, U+00ED): no debe cambiar.
        "Medellín, Antioquia",
        "Medellín, Antioquia",
    ),
    (
        # Mezcla: "Bogota" con tilde real + "tecnico" roto.
        "Bogotá · tÃ©cnico",
        "Bogotá · técnico",
    ),
    (
        # Irrecuperable (U+FFFD ya perdio los bytes en origen): sin cambios.
        "construcci�n",
        "construcci�n",
    ),
    (None, None),
    ("", ""),
]


@pytest.mark.parametrize(("entrada", "esperado"), CASOS_REPARAR_TEXTO)
def test_reparar_texto_arregla_mojibake_por_segmentos(entrada, esperado):
    assert reparar_texto(entrada) == esperado


def test_reparar_texto_nunca_lanza_con_entradas_raras():
    # Emojis y signos fuera de cp1252: deben quedar intactos, nunca lanzar.
    texto = "\U0001f3af ¡Únete!"
    assert reparar_texto(texto) == texto


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Desarrollador/a Java/PHP 1626256994-142", "Desarrollador/a Java/PHP"),
        ("Desarrollador/a Java 306886-155658", "Desarrollador/a Java"),
        (
            "Desarrollador/a de software I con o sin discapacidad 362338-141722",
            "Desarrollador/a de software I con o sin discapacidad",
        ),
        (
            "Desarrollador/a Open Smartflex Con O Sin Discapacidad 626040293-357",
            "Desarrollador/a Open Smartflex Con O Sin Discapacidad",
        ),
        ("Auxiliar Punto de Venta Temporal - 147130", "Auxiliar Punto de Venta Temporal - 147130"),
        (
            "PROGRAMADORA CAM | MOLDES INDUSTRIALES Y CNC 5 EJES",
            "PROGRAMADORA CAM | MOLDES INDUSTRIALES Y CNC 5 EJES",
        ),
        ("Desarrollador .NET", "Desarrollador .NET"),
        (None, None),
        ("", ""),
    ],
)
def test_limpiar_titulo_quita_el_codigo_interno_final(entrada, esperado):
    assert limpiar_titulo(entrada) == esperado
