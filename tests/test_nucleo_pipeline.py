from datetime import UTC, date, datetime

from boletin_empleos.config import (
    Config,
    ConfigExperiencia,
    UmbralesLegitimidad,
    Vocabulario,
)
from boletin_empleos.modelos import Decision, Modalidad, MotivoDescarte, Oferta
from boletin_empleos.nucleo.deduplicacion import clave_dedup, deduplicar
from boletin_empleos.nucleo.pipeline import evaluar

HOY = date(2026, 9, 9)
CONFIANZA = {"spe": 0.95, "magneto": 0.80, "remoteok": 0.70}

CFG = Config(
    destinatarios=["a@b.co"],
    remitente="a@b.co",
    asunto="Boletín",
    umbral_relevancia=0.35,
    dias_max_antiguedad=30,
    max_meses_experiencia=60,
    excluir_practicas=True,
    vocabulario=Vocabulario(
        cargos=["desarrollador", "backend"],
        tecnologias=["python"],
        excluidos=["call center"],
    ),
    experiencia=ConfigExperiencia(terminos_excluidos=["senior"]),
    legitimidad=UmbralesLegitimidad(
        min_caracteres_descripcion=10,
        frases_descarte=["inversion inicial"],
        frases_sospechosas=[],
        dominios_sospechosos=[],
    ),
)
DESC = "Buscamos desarrollador con Python para nuestro equipo de tecnología."


def _oferta(id_: str, fuente: str, titulo: str, **extra) -> Oferta:
    base = dict(
        id=id_,
        fuente=fuente,
        titulo=titulo,
        empresa="Acme S.A.S.",
        ubicacion="Armenia, Quindío",
        modalidad=Modalidad.PRESENCIAL,
        url=f"https://ejemplo.co/{id_}",
        descripcion=DESC,
        recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
    )
    return Oferta(**(base | extra))


def test_clave_dedup_ignora_mayusculas_tildes_y_fuente():
    a = _oferta("spe:1", "spe", "Desarrollador Backend")
    b = _oferta("magneto:9", "magneto", "  desarrollador  backend ")
    assert clave_dedup(a) == clave_dedup(b)


def test_deduplicar_conserva_la_fuente_mas_confiable():
    a = _oferta("magneto:9", "magneto", "Desarrollador Backend")
    b = _oferta("spe:1", "spe", "Desarrollador Backend")
    unicas, duplicadas = deduplicar([a, b], CONFIANZA)
    assert len(unicas) == 1
    assert unicas[0].fuente == "spe"
    assert [d.fuente for d in duplicadas] == ["magneto"]


def test_evaluar_incluye_una_oferta_pertinente():
    r = evaluar([_oferta("spe:1", "spe", "Desarrollador Backend")], set(), CFG, CONFIANZA, HOY)
    assert len(r.incluidas) == 1
    assert r.incluidas[0].decision is Decision.INCLUIR
    assert r.descartadas == []


def test_evaluar_descarta_por_relevancia():
    o = _oferta("spe:2", "spe", "Agente de Call Center", descripcion="Atención telefónica.")
    r = evaluar([o], set(), CFG, CONFIANZA, HOY)
    assert r.incluidas == []
    assert r.descartadas[0].motivo is MotivoDescarte.RELEVANCIA


def test_evaluar_descarta_por_experiencia():
    r = evaluar(
        [_oferta("spe:3", "spe", "Senior Desarrollador Backend")], set(), CFG, CONFIANZA, HOY
    )
    assert r.descartadas[0].motivo is MotivoDescarte.EXPERIENCIA


def test_evaluar_descarta_practicas_porque_la_audiencia_son_egresados():
    o = _oferta("spe:4", "spe", "Desarrollador Backend", es_practica=True)
    r = evaluar([o], set(), CFG, CONFIANZA, HOY)
    assert r.descartadas[0].motivo is MotivoDescarte.ES_PRACTICA


def test_evaluar_descarta_por_legitimidad():
    o = _oferta("spe:5", "spe", "Desarrollador Backend", descripcion=DESC + " Inversion inicial.")
    r = evaluar([o], set(), CFG, CONFIANZA, HOY)
    assert r.descartadas[0].motivo is MotivoDescarte.LEGITIMIDAD
    assert r.descartadas[0].notas


def test_evaluar_omite_lo_ya_enviado_en_ediciones_anteriores():
    o = _oferta("spe:6", "spe", "Desarrollador Backend")
    r = evaluar([o], {"spe:6"}, CFG, CONFIANZA, HOY)
    assert r.incluidas == []
    assert r.conteos["ya_enviadas"] == 1


def test_los_conteos_cuadran_con_lo_procesado():
    ofertas = [
        _oferta("spe:1", "spe", "Desarrollador Backend"),
        _oferta("spe:2", "spe", "Agente de Call Center", descripcion="Atención telefónica."),
        _oferta("spe:3", "spe", "Senior Desarrollador Backend"),
    ]
    r = evaluar(ofertas, set(), CFG, CONFIANZA, HOY)
    assert r.conteos["recibidas"] == 3
    assert r.conteos["incluidas"] == len(r.incluidas)
