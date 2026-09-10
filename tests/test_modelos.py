# tests/test_modelos.py
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from boletin_empleos.modelos import Decision, Evaluacion, Modalidad, MotivoDescarte, Oferta


def _oferta(**extra) -> Oferta:
    base = dict(
        id="spe:123",
        fuente="spe",
        titulo="Desarrollador Backend Python",
        empresa="Acme S.A.S.",
        ubicacion="Armenia, Quindío",
        pais="CO",
        modalidad=Modalidad.PRESENCIAL,
        url="https://ejemplo.co/vacante/123",
        descripcion="Se requiere desarrollador con conocimientos en Python y SQL.",
        recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
    )
    return Oferta(**(base | extra))


def test_oferta_minima_valida():
    o = _oferta()
    assert o.id == "spe:123"
    assert o.modalidad is Modalidad.PRESENCIAL
    assert o.fecha_publicacion is None
    assert o.es_practica is False


def test_oferta_acepta_campos_del_spe():
    o = _oferta(
        fecha_publicacion=date(2026, 9, 1),
        fecha_vencimiento=date(2026, 10, 1),
        meses_experiencia=12,
        es_practica=True,
        salario_min=3_000_000,
        salario_max=4_000_000,
        moneda="COP",
    )
    assert o.meses_experiencia == 12
    assert o.es_practica is True
    assert o.salario_max == 4_000_000


def test_oferta_rechaza_url_invalida():
    with pytest.raises(ValidationError):
        _oferta(url="no-es-una-url")


def test_evaluacion_conserva_motivo_y_notas():
    e = Evaluacion(
        oferta=_oferta(),
        puntaje_relevancia=0.9,
        puntaje_legitimidad=0.8,
        decision=Decision.DESCARTAR,
        motivo=MotivoDescarte.LEGITIMIDAD,
        notas=["contacto solo por WhatsApp"],
    )
    assert e.decision is Decision.DESCARTAR
    assert e.motivo is MotivoDescarte.LEGITIMIDAD
    assert e.notas == ["contacto solo por WhatsApp"]


def test_evaluacion_incluida_no_tiene_motivo():
    e = Evaluacion(
        oferta=_oferta(),
        puntaje_relevancia=0.9,
        puntaje_legitimidad=0.9,
        decision=Decision.INCLUIR,
    )
    assert e.motivo is None
    assert e.notas == []
