"""El modelo de la edición: qué archivo es válido y qué cuenta como pendiente."""

import pytest
from conftest import leer_datos
from pydantic import ValidationError

from boletin_semestral.modelo import Edicion, antetitulo, fotos_nombradas, pendientes


def _edicion(carpeta, **cambios) -> Edicion:
    datos = leer_datos(carpeta)
    datos.update(cambios)
    return Edicion.model_validate(datos)


def test_una_edicion_completa_valida_y_no_tiene_pendientes(carpeta_edicion):
    edicion = _edicion(carpeta_edicion)

    assert edicion.volumen == 8
    assert len(edicion.secciones) == 6
    assert pendientes(edicion) == []


def test_tipo_desconocido_falla(carpeta_edicion):
    datos = leer_datos(carpeta_edicion)
    datos["secciones"][0]["tipo"] = "foto"

    with pytest.raises(ValidationError):
        Edicion.model_validate(datos)


def test_porcentaje_fuera_de_rango_falla(carpeta_edicion):
    datos = leer_datos(carpeta_edicion)
    datos["secciones"][3]["grupos"][0]["indicadores"][0]["actual"] = 101

    with pytest.raises(ValidationError):
        Edicion.model_validate(datos)


def test_enlace_de_video_sin_https_falla(carpeta_edicion):
    datos = leer_datos(carpeta_edicion)
    datos["secciones"][4]["videos"][0]["enlace"] = "http://www.youtube.com/watch?v=abc123XYZ00"

    with pytest.raises(ValidationError):
        Edicion.model_validate(datos)


def test_semestre_mal_escrito_falla(carpeta_edicion):
    with pytest.raises(ValidationError):
        _edicion(carpeta_edicion, semestre="2026-3")


def test_campo_desconocido_falla(carpeta_edicion):
    datos = leer_datos(carpeta_edicion)
    datos["secciones"][0]["color"] = "rojo"

    with pytest.raises(ValidationError):
        Edicion.model_validate(datos)


def test_seccion_marcada_pendiente_cuenta(carpeta_edicion):
    datos = leer_datos(carpeta_edicion)
    datos["secciones"][1]["pendiente"] = "Falta X"

    resultado = pendientes(Edicion.model_validate(datos))

    assert len(resultado) == 1
    assert resultado[0].motivo == "Falta X"
    assert resultado[0].lugar == "02 · Planeta — Nuestro compromiso con el *planeta*"


def test_seccion_sin_contenido_minimo_cuenta(carpeta_edicion):
    datos = leer_datos(carpeta_edicion)
    datos["secciones"][1]["cuerpo"] = ""
    datos["secciones"][0]["cifras"] = []
    del datos["secciones"][5]["archivo"]

    resultado = pendientes(Edicion.model_validate(datos))

    assert len(resultado) == 3
    assert all(p.motivo == "Sin contenido" for p in resultado)
    lugares = " ".join(p.lugar for p in resultado)
    assert "01 · Cifras" in lugares
    assert "02 · Planeta" in lugares
    assert "06 · Sistema" in lugares


def test_portada_sin_titular_y_editorial_sin_cuerpo_cuentan(carpeta_edicion):
    datos = leer_datos(carpeta_edicion)
    datos["portada"]["titular"] = ""
    datos["editorial"]["cuerpo"] = ""

    lugares = [p.lugar for p in pendientes(Edicion.model_validate(datos))]

    assert lugares == ["Portada", "Editorial"]


def test_antetitulo_numera_desde_uno_con_dos_cifras(carpeta_edicion):
    edicion = _edicion(carpeta_edicion)

    assert antetitulo(1, edicion.secciones[1]) == "02 · Planeta"


def test_fotos_nombradas_sin_repetir_en_orden(carpeta_edicion):
    edicion = _edicion(carpeta_edicion)

    assert fotos_nombradas(edicion) == ["portada.jpg", "siembra.jpg", "taller.jpg", "sistema.png"]
