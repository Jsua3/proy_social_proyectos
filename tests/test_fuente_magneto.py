# tests/test_fuente_magneto.py
from pathlib import Path

import httpx
import respx

from boletin_empleos.fuentes.magneto import FuenteMagneto

FIXTURE = (Path(__file__).parent / "fixtures" / "magneto_listado.html").read_text("utf-8")


@respx.mock
def test_magneto_extrae_ofertas_del_listado():
    respx.get(url__startswith="https://www.magneto365.com/co/trabajos/").mock(
        return_value=httpx.Response(200, text=FIXTURE)
    )
    ofertas = FuenteMagneto(rutas=["/co/trabajos/buscar"]).obtener()

    assert len(ofertas) >= 15, "la fixture real trae ~20 tarjetas; menos indica selectores rotos"
    o = ofertas[0]
    assert o.fuente == "magneto"
    assert o.pais == "CO"
    assert o.titulo.strip()
    assert str(o.url).startswith("https://www.magneto365.com/co/empleos/")
    assert o.empresa, "la empresa sale del segundo segmento del texto de la tarjeta"


@respx.mock
def test_magneto_una_ruta_caida_no_tumba_las_demas():
    """La ruta de trabajo remoto devuelve HTTP 500 desde el servidor de Magneto."""
    respx.get("https://www.magneto365.com/co/trabajos/rota").mock(return_value=httpx.Response(500))
    respx.get("https://www.magneto365.com/co/trabajos/buscar").mock(
        return_value=httpx.Response(200, text=FIXTURE)
    )
    ofertas = FuenteMagneto(rutas=["/co/trabajos/rota", "/co/trabajos/buscar"], pausa=0.0).obtener()
    assert ofertas, "una ruta caída no debe impedir que las demás aporten"


@respx.mock
def test_magneto_nunca_pide_urls_con_parametros():
    """robots.txt de Magneto: Disallow: /*? — y su llms.txt pide evitar parámetros."""
    ruta = respx.get(url__startswith="https://www.magneto365.com/co/trabajos/").mock(
        return_value=httpx.Response(200, text=FIXTURE)
    )
    FuenteMagneto(rutas=["/co/trabajos/ofertas-empleo-trabajo-remoto"]).obtener()

    for llamada in ruta.calls:
        assert not llamada.request.url.query, f"URL con parámetros: {llamada.request.url}"


def test_magneto_declara_su_permiso_y_atribucion():
    f = FuenteMagneto()
    assert f.nombre == "magneto"
    assert "llms.txt" in f.base_permiso
    assert "Magneto" in f.atribucion


@respx.mock
def test_magneto_devuelve_vacio_si_falla():
    respx.get(url__startswith="https://www.magneto365.com/co/trabajos/").mock(
        return_value=httpx.Response(404)
    )
    assert FuenteMagneto(rutas=["/co/trabajos/ofertas-empleo-trabajo-remoto"]).obtener() == []
