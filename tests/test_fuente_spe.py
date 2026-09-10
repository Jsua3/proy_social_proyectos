# tests/test_fuente_spe.py
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import respx

from boletin_empleos.fuentes.spe import FuenteSPE, _a_modalidad, _rango_salarial
from boletin_empleos.modelos import Modalidad

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "spe_pagina.json").read_text("utf-8"))


@respx.mock
def test_spe_pagina_y_normaliza():
    una_pagina = FIXTURE | {"totalPages": 1, "currentPage": 1}
    respx.get(url__startswith="https://www.buscadordeempleo.gov.co/backbue/v1").mock(
        return_value=httpx.Response(200, json=una_pagina)
    )
    ofertas = FuenteSPE(consultas=[{"departamento": "Quindio"}]).obtener()

    assert len(ofertas) == len(FIXTURE["resultados"])
    o = ofertas[0]
    assert o.fuente == "spe"
    assert o.id.startswith("spe:")
    assert o.pais == "CO"
    assert str(o.url).startswith("http"), "la URL sale de DETALLES_PRESTADOR[0].URL_DETALLE_VACANTE"
    assert o.empresa, "el nombre del prestador viene en DETALLES_PRESTADOR[0].NOMBRE_PRESTADOR"


@respx.mock
def test_spe_recorre_todas_las_paginas():
    llamadas = {"n": 0}

    def responder(request):
        # Solo se cuentan las páginas de resultados: /version también casa con este mock
        # y contarlo daría 4 en vez de 3.
        if "vacantes/resultados" in request.url.path:
            llamadas["n"] += 1
        pagina = int(request.url.params.get("page", 1))
        return httpx.Response(200, json=FIXTURE | {"totalPages": 3, "currentPage": pagina})

    respx.get(url__startswith="https://www.buscadordeempleo.gov.co/backbue/v1").mock(
        side_effect=responder
    )
    FuenteSPE(consultas=[{"departamento": "Quindio"}], pausa=0.0).obtener()
    assert llamadas["n"] == 3


def test_spe_extrae_url_y_prestador_de_la_lista():
    """DETALLES_PRESTADOR es una LISTA de dicts, no una cadena.

    Tratarla como cadena lanzaría AttributeError con cada registro del SPE.
    """
    from boletin_empleos.fuentes.spe import _prestador

    fila = FIXTURE["resultados"][0]
    nombre, url = _prestador(fila)
    assert nombre and url and url.startswith("http")

    assert _prestador({}) == (None, None)
    assert _prestador({"DETALLES_PRESTADOR": []}) == (None, None)
    assert _prestador({"DETALLES_PRESTADOR": "texto plano"}) == (None, None)


def test_spe_omite_vacantes_sin_url_de_detalle():
    from boletin_empleos.fuentes.spe import FuenteSPE

    fuente = FuenteSPE()
    sin_url = dict(FIXTURE["resultados"][0])
    sin_url["DETALLES_PRESTADOR"] = [{"NOMBRE_PRESTADOR": "X", "URL_DETALLE_VACANTE": ""}]
    assert fuente._normalizar(sin_url, datetime(2026, 9, 9, tzinfo=UTC)) is None


def test_spe_traduce_teletrabajo_a_modalidad():
    assert _a_modalidad("1") is Modalidad.REMOTO
    assert _a_modalidad("Si") is Modalidad.REMOTO
    assert _a_modalidad("0") is Modalidad.PRESENCIAL
    assert _a_modalidad(None) is Modalidad.PRESENCIAL


def test_spe_interpreta_el_rango_salarial():
    assert _rango_salarial("$1.000.001 - $1.500.000") == (1_000_001, 1_500_000)
    assert _rango_salarial("Mayor de $15.000.001") == (15_000_001, None)
    assert _rango_salarial("A Convenir") == (None, None)
    assert _rango_salarial(None) == (None, None)


def test_spe_declara_su_permiso_y_atribucion():
    f = FuenteSPE()
    assert f.nombre == "spe"
    assert f.confianza_base == 0.95
    assert "Servicio Público de Empleo" in f.atribucion


@respx.mock
def test_spe_devuelve_vacio_si_la_api_falla(monkeypatch):
    monkeypatch.setattr("boletin_empleos.http.time.sleep", lambda _: None)
    respx.get(url__startswith="https://www.buscadordeempleo.gov.co/backbue/v1").mock(
        return_value=httpx.Response(502)
    )
    assert FuenteSPE(consultas=[{"departamento": "Quindio"}]).obtener() == []


@respx.mock
def test_spe_devuelve_vacio_si_el_cuerpo_no_es_json():
    """Un 200 con HTML — mantenimiento, interstitial de WAF — no debe lanzar excepción."""
    respx.get(url__startswith="https://www.buscadordeempleo.gov.co/backbue/v1").mock(
        return_value=httpx.Response(200, text="<html>Mantenimiento</html>")
    )
    assert FuenteSPE(consultas=[{"departamento": "Quindio"}]).obtener() == []
