from datetime import UTC, datetime
from pathlib import Path

import pytest

from boletin_empleos.config import cargar_config
from boletin_empleos.modelos import Modalidad, Oferta
from boletin_empleos.nucleo.experiencia import experiencia_apropiada
from boletin_empleos.nucleo.relevancia import puntuar_relevancia

RAIZ = Path(__file__).resolve().parents[1]


def test_carga_el_config_del_proyecto():
    cfg = cargar_config(RAIZ / "config.toml")

    assert cfg.destinatarios, "debe haber al menos un destinatario"
    assert cfg.vocabulario.cargos, "el vocabulario de cargos no puede estar vacío"
    assert cfg.vocabulario.tecnologias
    assert 0.0 < cfg.umbral_relevancia <= 1.0
    assert cfg.dias_max_antiguedad > 0
    assert cfg.legitimidad.frases_descarte
    assert cfg.legitimidad.min_caracteres_descripcion == 200


def test_los_terminos_del_vocabulario_estan_normalizados():
    cfg = cargar_config(RAIZ / "config.toml")
    todos = cfg.vocabulario.cargos + cfg.vocabulario.tecnologias
    assert all(t == t.lower().strip() for t in todos), (
        "deben venir en minúscula y sin espacios extra"
    )


# --- Ronda 2 — R2-3: vocabulario ajustado con las fugas del primer boletín real ---


def _oferta(titulo: str, descripcion: str = "") -> Oferta:
    return Oferta(
        id="x:1",
        fuente="x",
        titulo=titulo,
        modalidad=Modalidad.REMOTO,
        url="https://ejemplo.co/1",
        descripcion=descripcion,
        recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
    )


def _pasa_relevancia_y_experiencia(cfg, titulo: str, descripcion: str = "") -> bool:
    oferta = _oferta(titulo, descripcion)
    relevancia = puntuar_relevancia(oferta, cfg.vocabulario, cfg.relevancia)
    apropiado, _ = experiencia_apropiada(oferta, cfg.experiencia, cfg.max_meses_experiencia)
    return relevancia >= cfg.umbral_relevancia and apropiado


# Los 8 títulos que entraron al primer boletín real (14/09/2026) pese a no ser
# ofertas de software para egresados — spec ronda 2, R2-3. La descripción de
# cada caso es representativa del tipo de oferta real (comercial/ventas o
# mecanizado CNC), no la descripción original de esa corrida: el registro de
# esa corrida solo guardó los títulos, no el cuerpo completo de cada oferta.
CASOS_QUEDAN_FUERA = [
    (
        "Data Engineer Sr",
        "Buscamos Data Engineer con experiencia en pipelines de datos, Python y SQL.",
    ),
    (
        "Principal Data Engineer",
        "Buscamos Principal Data Engineer para liderar la arquitectura de datos en AWS y Python.",
    ),
    (
        "Desarrollador Experto de Sistemas de Informacion",
        "Se requiere desarrollador con experiencia en sistemas de información, Java y SQL.",
    ),
    (
        "Desarrollador Comercial HORECA (Clientes Premium)",
        "Buscamos ejecutivo con enfoque comercial en el sector HORECA, clientes premium y ventas.",
    ),
    (
        "Desarrollador/a comercial",
        "Se requiere profesional con experiencia en desarrollo comercial, "
        "cartera de clientes y ventas B2B.",
    ),
    (
        "Analista de Desarrollo Comercial",
        "El analista apoyará el desarrollo comercial de la organización y la gestión de clientes.",
    ),
    (
        "Desarrollador de Negocios Lubricantes Ibague",
        "Buscamos desarrollador de negocios para la línea de lubricantes en Ibagué, ventas B2B.",
    ),
    (
        "PROGRAMADORA CAM | MOLDES INDUSTRIALES Y CNC 5 EJES | REMOTO",
        "Se requiere programador de máquinas CNC de 5 ejes para moldes industriales, software CAM.",
    ),
]


@pytest.mark.parametrize(("titulo", "descripcion"), CASOS_QUEDAN_FUERA)
def test_r2_3_los_ocho_titulos_del_primer_boletin_real_quedan_fuera(titulo, descripcion):
    cfg = cargar_config(RAIZ / "config.toml")
    assert _pasa_relevancia_y_experiencia(cfg, titulo, descripcion) is False, titulo


CASOS_SIGUEN_ENTRANDO = [
    (
        "Desarrollador JR",
        "Se busca desarrollador junior con conocimientos en Python y bases de datos SQL.",
    ),
    (
        "Ingeniero QA Junior",
        "Se busca ingeniero QA junior para pruebas automatizadas con Selenium y SQL.",
    ),
    (
        "Desarrollador Backend Java",
        "Se busca desarrollador backend con experiencia en Java, Spring y microservicios.",
    ),
    (
        "Analista de desarrollo",
        "El analista de desarrollo trabajará en el mantenimiento de aplicaciones en Python y SQL.",
    ),
    (
        "Ingeniero de software",
        "Se busca ingeniero de software con experiencia en arquitecturas cloud, AWS y Docker.",
    ),
]


@pytest.mark.parametrize(("titulo", "descripcion"), CASOS_SIGUEN_ENTRANDO)
def test_r2_3_las_ofertas_de_software_legitimas_siguen_entrando(titulo, descripcion):
    """El ajuste de vocabulario no debe dejar fuera ofertas de software genuinas."""
    cfg = cargar_config(RAIZ / "config.toml")
    assert _pasa_relevancia_y_experiencia(cfg, titulo, descripcion) is True, titulo


def test_r2_3_sr_reemplaza_a_sr_punto_sin_perder_cobertura_ni_casar_en_sres():
    """ "sr." pasó a "sr": la frontera de palabra ya cubre "Sr" y "Sr." sin el

    punto, y "sr" no debe casar dentro de "Sres."."""
    cfg = cargar_config(RAIZ / "config.toml")
    assert "sr" in cfg.experiencia.terminos_excluidos
    assert "sr." not in cfg.experiencia.terminos_excluidos

    ok_sr, _ = experiencia_apropiada(
        _oferta("Data Engineer Sr"), cfg.experiencia, cfg.max_meses_experiencia
    )
    ok_sr_punto, _ = experiencia_apropiada(
        _oferta("Data Engineer Sr."), cfg.experiencia, cfg.max_meses_experiencia
    )
    ok_sres, _ = experiencia_apropiada(
        _oferta("Atención a Sres. Clientes"), cfg.experiencia, cfg.max_meses_experiencia
    )
    assert ok_sr is False
    assert ok_sr_punto is False
    assert ok_sres is True
