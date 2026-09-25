"""Keyrus — portal de empleo propio de la empresa, recomendado por la profesora.

La fixture es el feed real de jobs.keyrus.co recortado (descripciones acortadas).
"""

import json
from datetime import date
from pathlib import Path

import httpx
import respx

from boletin_empleos.fuentes.keyrus import FuenteKeyrus
from boletin_empleos.modelos import Modalidad

FEED = json.loads((Path(__file__).parent / "fixtures" / "keyrus_feed.json").read_text("utf-8"))
URL = "https://jobs.keyrus.co/jobs.json"


def _por_titulo(ofertas, fragmento):
    return next(o for o in ofertas if fragmento.lower() in o.titulo.lower())


def test_declara_su_base_de_permiso_como_toda_fuente():
    fuente = FuenteKeyrus()

    assert fuente.nombre == "keyrus"
    assert "robots.txt" in fuente.base_permiso
    assert "Keyrus" in fuente.atribucion
    assert fuente.url_atribucion.startswith("https://jobs.keyrus.co")
    assert 0.0 < fuente.confianza_base <= 1.0


@respx.mock
def test_normaliza_las_vacantes_del_feed():
    respx.get(URL).mock(return_value=httpx.Response(200, json=FEED))

    ofertas = FuenteKeyrus().obtener()

    assert len(ofertas) == len(FEED["items"])
    oferta = _por_titulo(ofertas, "Data Scientist")
    assert oferta.fuente == "keyrus"
    assert oferta.empresa == "Keyrus"
    assert str(oferta.url).startswith("https://jobs.keyrus.co/jobs/")
    assert oferta.fecha_publicacion == date(2026, 9, 2)
    assert "<p>" not in oferta.descripcion, "la descripción viaja en HTML y hay que limpiarla"
    assert len(oferta.descripcion) > 50


@respx.mock
def test_una_vacante_para_cualquier_ciudad_del_pais_es_remota():
    respx.get(URL).mock(return_value=httpx.Response(200, json=FEED))

    oferta = _por_titulo(FuenteKeyrus().obtener(), "Full Stack Developer")

    assert oferta.modalidad is Modalidad.REMOTO
    assert oferta.pais == "CO"
    assert "Colombia" in (oferta.ubicacion or "")


@respx.mock
def test_una_vacante_con_ciudad_concreta_es_presencial():
    respx.get(URL).mock(return_value=httpx.Response(200, json=FEED))

    oferta = _por_titulo(FuenteKeyrus().obtener(), "Data Scientist")

    assert oferta.modalidad is Modalidad.PRESENCIAL
    assert oferta.ubicacion == "Bogotá, Colombia"


@respx.mock
def test_entre_varios_paises_manda_Colombia():
    """El boletín es para egresados que viven aquí."""
    respx.get(URL).mock(return_value=httpx.Response(200, json=FEED))

    oferta = _por_titulo(FuenteKeyrus().obtener(), "Talent Pool")

    assert oferta.pais == "CO"


@respx.mock
def test_las_practicas_se_marcan_como_tales():
    """El boletín es para egresados; el filtro de prácticas decide después."""
    respx.get(URL).mock(return_value=httpx.Response(200, json=FEED))

    ofertas = FuenteKeyrus().obtener()

    assert _por_titulo(ofertas, "Interns Program").es_practica
    assert _por_titulo(ofertas, "Consulting Intern").es_practica
    assert not _por_titulo(ofertas, "Data Scientist").es_practica


@respx.mock
def test_lo_que_sigue_publicado_en_el_portal_sigue_vigente():
    """Un portal de empresa baja la vacante cuando la llena; un agregador no.

    Sin esto, la vacante que la profesora señaló —publicada en 2025— se caería
    por antigüedad aunque la empresa la siga ofreciendo hoy."""
    respx.get(URL).mock(return_value=httpx.Response(200, json=FEED))

    ofertas = FuenteKeyrus().obtener()

    assert all(o.vigencia_verificada for o in ofertas)


@respx.mock
def test_si_el_portal_falla_no_lanza_y_devuelve_vacio():
    respx.get(URL).mock(return_value=httpx.Response(503))

    assert FuenteKeyrus().obtener() == []


@respx.mock
def test_una_vacante_mal_formada_no_se_lleva_a_las_demas():
    roto = {"items": [{"id": "x"}, *FEED["items"][:1]]}
    respx.get(URL).mock(return_value=httpx.Response(200, json=roto))

    ofertas = FuenteKeyrus().obtener()

    assert len(ofertas) == 1
