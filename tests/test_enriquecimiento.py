# tests/test_enriquecimiento.py
from datetime import UTC, datetime

from boletin_empleos.enriquecimiento import crear_enriquecedor
from boletin_empleos.enriquecimiento.nulo import EnriquecedorNulo
from boletin_empleos.modelos import Decision, Evaluacion, Modalidad, Oferta


def _evaluacion() -> Evaluacion:
    return Evaluacion(
        oferta=Oferta(
            id="x:1",
            fuente="x",
            titulo="Desarrollador",
            modalidad=Modalidad.REMOTO,
            url="https://ejemplo.co/1",
            descripcion="Descripción larga de la vacante.",
            recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
        ),
        puntaje_relevancia=0.9,
        puntaje_legitimidad=0.9,
        decision=Decision.INCLUIR,
    )


def test_sin_api_key_se_usa_el_enriquecedor_nulo():
    assert isinstance(crear_enriquecedor(None), EnriquecedorNulo)
    assert isinstance(crear_enriquecedor(""), EnriquecedorNulo)


def test_el_enriquecedor_nulo_no_rompe_nada():
    e = EnriquecedorNulo()
    assert e.resumir([_evaluacion()]) == {}
    assert isinstance(e.editorial([_evaluacion()], {"incluidas": 1}), str)
    assert e.editorial([_evaluacion()], {"incluidas": 1}), "debe dar un texto fijo, no vacío"


def test_anthropic_cae_a_nulo_si_el_proveedor_falla(monkeypatch):
    from boletin_empleos.enriquecimiento.anthropic import EnriquecedorAnthropic

    e = EnriquecedorAnthropic(api_key="clave-falsa")

    def explotar(*args, **kwargs):
        raise RuntimeError("proveedor caído")

    monkeypatch.setattr(e, "_pedir", explotar)

    assert e.resumir([_evaluacion()]) == {}
    assert e.editorial([_evaluacion()], {"incluidas": 1})
