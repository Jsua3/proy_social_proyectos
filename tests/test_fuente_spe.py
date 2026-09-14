# tests/test_fuente_spe.py
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx

from boletin_empleos.fuentes.spe import (
    FuenteSPE,
    _a_modalidad,
    _meses_experiencia,
    _rango_salarial,
    _ubicacion,
)
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


@respx.mock
@pytest.mark.parametrize(
    ("cuerpo", "descripcion"),
    [
        ({"totalPages": "muchas", "resultados": []}, "totalPages como cadena"),
        ({"totalPages": 1, "resultados": None}, "resultados nulo"),
        ({"totalPages": 1, "resultados": {"a": 1}}, "resultados como objeto"),
        ({"totalPages": 1, "resultados": ["texto plano"]}, "elementos no-dict"),
        ({"totalPages": -5, "resultados": []}, "totalPages negativo"),
    ],
)
def test_spe_no_lanza_con_json_valido_pero_mal_tipado(cuerpo, descripcion):
    """Un JSON válido no garantiza tipos correctos. El adaptador nunca debe lanzar."""
    respx.get(url__startswith="https://www.buscadordeempleo.gov.co/backbue/v1").mock(
        return_value=httpx.Response(200, json=cuerpo)
    )
    assert FuenteSPE(consultas=[{"departamento": "Quindio"}], pausa=0.0).obtener() == [], (
        descripcion
    )


def test_contexto_ssl_carga_el_intermedio_sin_bajar_la_verificacion():
    """El servidor del SPE omite su intermedio; lo aportamos sin desactivar nada."""
    import ssl

    from boletin_empleos.http import contexto_ssl

    contexto = contexto_ssl(["geotrust-tls-rsa-ca-g1.pem"])
    assert contexto.verify_mode is ssl.CERT_REQUIRED, "la verificación debe seguir activa"
    assert contexto.check_hostname is True, "la comprobación de host debe seguir activa"
    # El intermedio quedó realmente cargado en el almacén del contexto.
    sujetos = [
        dict(x for parte in cert["subject"] for x in parte).get("commonName", "")
        for cert in contexto.get_ca_certs()
    ]
    assert "GeoTrust TLS RSA CA G1" in sujetos


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


# --- Ronda 2 -----------------------------------------------------------------


@respx.mock
def test_spe_repara_el_mojibake_del_titulo_antes_de_construir_la_oferta():
    """R2-1: el SPE entrega UTF-8 mal leído como cp1252; los filtros deben ver

    el texto ya reparado, no el roto — por eso se repara ANTES de armar la
    Oferta, y por eso se prueba aquí y no solo en `reparar_texto` suelta.
    """
    fila = dict(FIXTURE["resultados"][0])
    fila["TITULO_VACANTE"] = "Lider tÃ©cnico/a QA"
    una_pagina = FIXTURE | {"resultados": [fila], "totalPages": 1, "currentPage": 1}
    respx.get(url__startswith="https://www.buscadordeempleo.gov.co/backbue/v1").mock(
        return_value=httpx.Response(200, json=una_pagina)
    )
    ofertas = FuenteSPE(consultas=[{"departamento": "Quindio"}]).obtener()
    assert ofertas[0].titulo == "Lider técnico/a QA"


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (144, 12),
        (216, 18),
        (288, 24),
        (720, 60),
        (36, 36),
        (120, 120),
        (130, 130),
        (None, None),
        ("no es un número", None),
    ],
)
def test_meses_experiencia_corrige_meses_por_12(valor, esperado):
    """R2-2: algunas bolsas guardan MESES_EXPERIENCIA_CARGO como meses × 12.

    Evidencia real (valor del campo ↔ lo que dice la descripción): 216↔"18
    meses", 288↔"24 meses", 144↔"12 meses"; en cambio 36↔"3 años" y 12↔"un
    año" sí vienen en meses reales, y 120 o menos se deja igual porque 72 o 96
    podrían ser años reales sin forma de saberlo.
    """
    assert _meses_experiencia(valor) == esperado


@pytest.mark.parametrize(
    ("municipio", "departamento", "esperado"),
    [
        ("BOGOTÁ, D.C.", "BOGOTÁ, D.C.", "BOGOTÁ, D.C."),
        (
            "VACANTES PARA TODO EL TERRITORIO",
            "VACANTES PARA TODO EL TERRITORIO",
            "VACANTES PARA TODO EL TERRITORIO",
        ),
        ("DEPARTAMENTO CUNDINAMARCA", "CUNDINAMARCA", "DEPARTAMENTO CUNDINAMARCA"),
        ("MEDELLÍN", "ANTIOQUIA", "MEDELLÍN, ANTIOQUIA"),
        ("", "QUINDIO", "QUINDIO"),
    ],
)
def test_ubicacion_no_duplica_el_departamento(municipio, departamento, esperado):
    """R2-4: no se añade el departamento cuando ya está contenido en el

    municipio, comparando sin mayúsculas ni tildes.
    """
    assert _ubicacion(municipio, departamento) == esperado


@respx.mock
def test_spe_limpia_el_codigo_interno_del_titulo():
    """R2-5: algunas bolsas pegan su código de control al final del título."""
    fila = dict(FIXTURE["resultados"][0])
    fila["TITULO_VACANTE"] = "Desarrollador/a Java/PHP 1626256994-142"
    una_pagina = FIXTURE | {"resultados": [fila], "totalPages": 1, "currentPage": 1}
    respx.get(url__startswith="https://www.buscadordeempleo.gov.co/backbue/v1").mock(
        return_value=httpx.Response(200, json=una_pagina)
    )
    ofertas = FuenteSPE(consultas=[{"departamento": "Quindio"}]).obtener()
    assert ofertas[0].titulo == "Desarrollador/a Java/PHP"
