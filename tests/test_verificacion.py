from datetime import UTC, datetime

import httpx
import respx

from boletin_empleos.modelos import Decision, Evaluacion, Modalidad, MotivoDescarte, Oferta
from boletin_empleos.verificacion import filtrar_enlaces_vivos


def _evaluacion(url: str) -> Evaluacion:
    return Evaluacion(
        oferta=Oferta(
            id=f"x:{url[-1]}",
            fuente="x",
            titulo="Desarrollador",
            modalidad=Modalidad.REMOTO,
            url=url,
            descripcion="Descripción.",
            recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
        ),
        puntaje_relevancia=0.9,
        puntaje_legitimidad=0.9,
        decision=Decision.INCLUIR,
    )


@respx.mock
def test_separa_enlaces_vivos_de_muertos():
    respx.head("https://ejemplo.co/1").mock(return_value=httpx.Response(200))
    respx.head("https://ejemplo.co/2").mock(return_value=httpx.Response(404))

    vivas, muertas = filtrar_enlaces_vivos(
        [_evaluacion("https://ejemplo.co/1"), _evaluacion("https://ejemplo.co/2")]
    )
    assert [str(e.oferta.url) for e in vivas] == ["https://ejemplo.co/1"]
    assert muertas[0].decision is Decision.DESCARTAR
    assert muertas[0].motivo is MotivoDescarte.ENLACE_MUERTO


@respx.mock
def test_cae_a_get_si_head_no_esta_permitido():
    respx.head("https://ejemplo.co/3").mock(return_value=httpx.Response(405))
    respx.get("https://ejemplo.co/3").mock(return_value=httpx.Response(200))

    vivas, muertas = filtrar_enlaces_vivos([_evaluacion("https://ejemplo.co/3")])
    assert len(vivas) == 1
    assert muertas == []


@respx.mock
def test_un_error_de_red_no_mata_la_oferta():
    """Ante la duda se conserva: es peor perder una vacante buena que mostrar una dudosa."""
    respx.head("https://ejemplo.co/4").mock(side_effect=httpx.ConnectTimeout("timeout"))
    respx.get("https://ejemplo.co/4").mock(side_effect=httpx.ConnectTimeout("timeout"))

    vivas, muertas = filtrar_enlaces_vivos([_evaluacion("https://ejemplo.co/4")])
    assert len(vivas) == 1
    assert muertas == []


@respx.mock
def test_un_403_no_es_un_enlace_muerto():
    """Medido el 22/09/2026: 448 de las 482 vacantes que el boletín de Industrial

    daba por muertas eran enlaces de Computrabajo, que responde 403 a cualquier
    petición automática. Un navegador las abre sin problema. Un 403 dice "a ti
    no", no "ya no existe": botarlas costaba dos tercios de la edición."""
    respx.head("https://portal.co/bloqueada").mock(return_value=httpx.Response(403))
    respx.get("https://portal.co/bloqueada").mock(return_value=httpx.Response(403))

    vivas, muertas = filtrar_enlaces_vivos([_evaluacion("https://portal.co/bloqueada")])

    assert len(vivas) == 1
    assert not muertas


@respx.mock
def test_un_error_del_servidor_tampoco_mata_la_oferta():
    """Un 500 puede ser un problema pasajero del portal; la vacante sigue ahí."""
    respx.head("https://portal.co/caido").mock(return_value=httpx.Response(500))

    vivas, muertas = filtrar_enlaces_vivos([_evaluacion("https://portal.co/caido")])

    assert len(vivas) == 1
    assert not muertas


@respx.mock
def test_un_404_si_es_un_enlace_muerto():
    respx.head("https://portal.co/borrada").mock(return_value=httpx.Response(404))

    vivas, muertas = filtrar_enlaces_vivos([_evaluacion("https://portal.co/borrada")])

    assert not vivas
    assert muertas[0].motivo is MotivoDescarte.ENLACE_MUERTO
