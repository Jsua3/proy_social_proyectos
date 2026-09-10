from datetime import UTC, date, datetime

from boletin_empleos.config import ConfigExperiencia, Vocabulario
from boletin_empleos.modelos import Modalidad, Oferta
from boletin_empleos.nucleo.experiencia import experiencia_apropiada
from boletin_empleos.nucleo.relevancia import normalizar_texto, puntuar_relevancia
from boletin_empleos.nucleo.vigencia import esta_vigente

VOCAB = Vocabulario(
    cargos=["desarrollador", "ingeniero de software", "backend"],
    tecnologias=["python", "java", "react"],
    excluidos=["asesor comercial", "call center"],
)
HOY = date(2026, 9, 9)


def _oferta(titulo: str, descripcion: str = "", **extra) -> Oferta:
    base = dict(
        id="x:1",
        fuente="x",
        titulo=titulo,
        modalidad=Modalidad.REMOTO,
        url="https://ejemplo.co/1",
        descripcion=descripcion,
        recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
    )
    return Oferta(**(base | extra))


def test_normalizar_texto_quita_tildes_y_baja_a_minuscula():
    assert normalizar_texto("Ingeniería de SOFTWARE") == "ingenieria de software"


def test_relevancia_alta_cuando_el_cargo_esta_en_el_titulo():
    o = _oferta("Desarrollador Backend", "Se requiere experiencia en Python y React.")
    assert puntuar_relevancia(o, VOCAB) > 0.6


def test_relevancia_baja_para_oferta_no_tecnica():
    o = _oferta("Auxiliar de enfermería", "Atención a pacientes en Armenia.")
    assert puntuar_relevancia(o, VOCAB) < 0.2


def test_termino_excluido_anula_la_relevancia():
    o = _oferta("Asesor Comercial", "Manejo de Python para reportes internos.")
    assert puntuar_relevancia(o, VOCAB) == 0.0


def test_el_titulo_pesa_mas_que_la_descripcion():
    en_titulo = _oferta("Desarrollador", "Sin más detalles.")
    en_descripcion = _oferta("Profesional TI", "Buscamos un desarrollador para el equipo.")
    assert puntuar_relevancia(en_titulo, VOCAB) > puntuar_relevancia(en_descripcion, VOCAB)


CFG_EXPERIENCIA = ConfigExperiencia(terminos_excluidos=["senior", "lead", "jefe de"])


def test_experiencia_rechaza_cargos_senior():
    ok, motivo = experiencia_apropiada(_oferta("Senior Backend Developer"), CFG_EXPERIENCIA, 60)
    assert ok is False
    assert "senior" in motivo


def test_experiencia_rechaza_por_exceso():
    ok, motivo = experiencia_apropiada(
        _oferta("Desarrollador", meses_experiencia=84), CFG_EXPERIENCIA, 60
    )
    assert ok is False
    assert "84" in motivo


def test_experiencia_acepta_junior():
    ok, motivo = experiencia_apropiada(
        _oferta("Desarrollador Junior", meses_experiencia=12), CFG_EXPERIENCIA, 60
    )
    assert ok is True
    assert motivo == ""


def test_vigencia_usa_la_fecha_de_vencimiento_cuando_existe():
    vencida = _oferta("Dev", fecha_vencimiento=date(2026, 9, 1))
    viva = _oferta("Dev", fecha_vencimiento=date(2026, 10, 1))
    assert esta_vigente(vencida, HOY, 30)[0] is False
    assert esta_vigente(viva, HOY, 30)[0] is True


def test_vigencia_usa_la_antiguedad_si_no_hay_vencimiento():
    vieja = _oferta("Dev", fecha_publicacion=date(2026, 7, 1))
    reciente = _oferta("Dev", fecha_publicacion=date(2026, 9, 5))
    assert esta_vigente(vieja, HOY, 30)[0] is False
    assert esta_vigente(reciente, HOY, 30)[0] is True


def test_vigencia_acepta_cuando_no_hay_ninguna_fecha():
    """Sin información no se castiga: el enlace se verificará después."""
    assert esta_vigente(_oferta("Dev"), HOY, 30)[0] is True
