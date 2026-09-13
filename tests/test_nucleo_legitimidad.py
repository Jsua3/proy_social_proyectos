from datetime import UTC, datetime

import pytest

from boletin_empleos.config import UmbralesLegitimidad
from boletin_empleos.modelos import Modalidad, Oferta
from boletin_empleos.nucleo.legitimidad import puntuar_legitimidad

CFG = UmbralesLegitimidad(
    min_caracteres_descripcion=200,
    salario_minimo_legal=1_623_500,
    salario_maximo_razonable=25_000_000,
    frases_descarte=["inversion inicial", "kit de trabajo"],
    frases_sospechosas=["altos ingresos", "gana desde casa", "escribe al whatsapp"],
    dominios_sospechosos=["bit.ly", "t.me"],
)
DESC_LARGA = "Buscamos desarrollador para nuestro equipo. " * 10


def _oferta(**extra) -> Oferta:
    base = dict(
        id="x:1",
        fuente="x",
        titulo="Desarrollador Backend",
        empresa="Acme S.A.S.",
        modalidad=Modalidad.REMOTO,
        url="https://ejemplo.co/1",
        descripcion=DESC_LARGA,
        recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
    )
    return Oferta(**(base | extra))


def test_oferta_limpia_conserva_la_confianza_de_la_fuente():
    puntaje, notas = puntuar_legitimidad(_oferta(), 0.95, CFG)
    assert puntaje == 0.95
    assert notas == []


def test_pedir_dinero_al_aspirante_anula_la_oferta():
    o = _oferta(descripcion=DESC_LARGA + " Se requiere una inversion inicial de $200.000.")
    puntaje, notas = puntuar_legitimidad(o, 0.95, CFG)
    assert puntaje == 0.0
    assert any("inversion inicial" in n for n in notas)


def test_sin_empresa_y_con_contacto_por_mensajeria_anula():
    o = _oferta(empresa=None, descripcion=DESC_LARGA + " Escribe al whatsapp 300 000 0000.")
    puntaje, notas = puntuar_legitimidad(o, 0.95, CFG)
    assert puntaje == 0.0
    assert any("sin empresa" in n.lower() for n in notas)


def test_frases_sospechosas_penalizan_sin_anular():
    o = _oferta(descripcion=DESC_LARGA + " Altos ingresos garantizados.")
    puntaje, notas = puntuar_legitimidad(o, 0.95, CFG)
    assert 0.0 < puntaje < 0.95
    assert notas


def test_dominio_acortado_penaliza_fuerte():
    o = _oferta(url="https://bit.ly/vacante123")
    puntaje, notas = puntuar_legitimidad(o, 0.95, CFG)
    assert puntaje < 0.6
    assert any("bit.ly" in n for n in notas)


@pytest.mark.parametrize(
    ("url", "penalizada"),
    [
        ("https://bit.ly/vacante123", True),
        ("https://www.bit.ly/vacante123", True),  # subdominio del acortador
        ("https://export.media/vacante", False),  # contiene "t.me" como subcadena
        ("https://smart.mercadolibre.com/x", False),  # también contiene "t.me"
        ("https://cutt.ly.empresa.co/x", False),  # rótulo dentro de un dominio ajeno
    ],
)
def test_dominio_sospechoso_se_compara_contra_el_host(url, penalizada):
    """Por subcadena de la URL, "t.me" casaría dentro de export.media."""
    puntaje, _ = puntuar_legitimidad(_oferta(url=url), 0.95, CFG)
    assert (puntaje < 0.95) is penalizada


def test_salario_fuera_de_rango_penaliza():
    alto = _oferta(salario_min=80_000_000, moneda="COP")
    bajo = _oferta(salario_max=500_000, moneda="COP")
    assert puntuar_legitimidad(alto, 0.95, CFG)[0] < 0.95
    assert puntuar_legitimidad(bajo, 0.95, CFG)[0] < 0.95


def test_solo_penaliza_salario_en_pesos_colombianos():
    """Un salario en USD es normal para remoto internacional y no debe penalizarse."""
    o = _oferta(salario_min=90_000, moneda="USD")
    assert puntuar_legitimidad(o, 0.75, CFG)[0] == 0.75


def test_descripcion_muy_corta_penaliza_levemente():
    o = _oferta(descripcion="Se busca dev.")
    puntaje, notas = puntuar_legitimidad(o, 0.95, CFG)
    assert 0.7 < puntaje < 0.95
    assert any("descripción" in n for n in notas)


def test_el_puntaje_nunca_sale_del_rango():
    o = _oferta(
        empresa=None,
        url="https://t.me/canal",
        salario_min=99_000_000,
        moneda="COP",
        descripcion="corta",
    )
    puntaje, _ = puntuar_legitimidad(o, 0.70, CFG)
    assert 0.0 <= puntaje <= 1.0
