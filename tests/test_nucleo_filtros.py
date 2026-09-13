from datetime import UTC, date, datetime

import pytest

from boletin_empleos.config import ConfigExperiencia, Vocabulario
from boletin_empleos.modelos import Modalidad, Oferta
from boletin_empleos.nucleo.experiencia import experiencia_apropiada
from boletin_empleos.nucleo.relevancia import (
    admite_flexion,
    contiene,
    normalizar_texto,
    puntuar_relevancia,
)
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


@pytest.mark.parametrize(
    "titulo",
    [
        "Analista de Negocios",
        "Auxiliar de Servicios Generales",
        "Coordinador de Estudios",
        "Jardinero y Oficios Varios",
        "Asesor de Medios",
        "Operario de Vidrios",
    ],
)
def test_relevancia_no_casa_terminos_dentro_de_otras_palabras(titulo):
    """`ios` no debe casar dentro de negocios, servicios, estudios, oficios...

    Medido sobre 50 ofertas reales del SPE: con emparejamiento por subcadena, la
    única que pasaba el filtro era "Jardinero y Oficios Varios".
    """
    vocabulario = Vocabulario(cargos=["desarrollador"], tecnologias=["ios", "qa", "sre"])
    assert puntuar_relevancia(_oferta(titulo), vocabulario) == 0.0


@pytest.mark.parametrize(
    ("termino", "titulo", "debe_casar"),
    [
        ("ios", "Desarrollador iOS Senior", True),
        ("ios", "Analista de Negocios", False),
        ("qa", "Analista QA", True),
        ("qa", "Asesor en Qatar", False),
        (".net", "Desarrollador ASP.NET Core", True),
        (".net", "Técnico en Planeta", False),
        ("c#", "Programador C# Junior", True),
        ("java", "Desarrollador Java", True),
        ("java", "Analista JavaScript", False),
        ("sql", "Administrador SQL Server", True),
        ("sql", "Consultor NoSQL", False),
        ("git", "Manejo de Git", True),
        ("git", "Digitador", False),
        # Flexión española: las ofertas colombianas se escriben en femenino y plural.
        ("desarrollador", "Desarrolladora Backend", True),
        ("programador", "Programadora Python", True),
        ("desarrollador", "Desarrolladores Senior", True),
        # ...sin que la concesión abra colisiones nuevas:
        ("director", "Analista de Directorio Activo", False),
        ("analista", "Analistica de Datos", False),
        # Los acrónimos cortos NO se flexionan, para que 'sre' no case en 'Sres.':
        ("sre", "Gerente de Sres. Clientes", False),
        ("sre", "Ingeniero SRE", True),
    ],
)
def test_contiene_respeta_las_fronteras_de_palabra(termino, titulo, debe_casar):
    """`.net` sí debe casar dentro de `asp.net`; `java` no dentro de `javascript`."""
    assert contiene(normalizar_texto(titulo), termino) is debe_casar


@pytest.mark.parametrize(
    ("termino", "esperado"),
    [
        # Sustantivos de agente: SÍ se flexionan.
        ("desarrollador", True),
        ("programador", True),
        ("vendedor", True),
        ("director", True),
        ("gerente", True),
        ("analista", True),
        ("mesero", True),
        ("vigilante", True),
        # Nombres propios de tecnología: NO. Cada uno colisionaba de verdad.
        ("docker", False),  # "Dockers", marca de ropa
        ("angular", False),  # "angulares", metalmecánica
        ("android", False),  # "androides"
        ("tester", False),  # "testeros", mueblería y colchonería
        ("python", False),
        ("kubernetes", False),
        # Acrónimos cortos: tampoco.
        ("ios", False),
        ("qa", False),
        ("sre", False),
        # Compuestos: la flexión iría al final de la frase y no serviría.
        ("ingeniero de sistemas", False),
    ],
)
def test_solo_se_flexionan_los_sustantivos_de_agente(termino, esperado):
    """La regla es morfológica, no una lista de excepciones que haya que auditar.

    Un criterio por longitud no bastaba: `docker` y `tester` tienen 6 caracteres.
    """
    assert admite_flexion(termino) is esperado


@pytest.mark.parametrize(
    "titulo",
    [
        "Asesor de Ventas - Tienda Dockers",
        "Técnico en corte de piezas angulares",
        "Operario de estructuras angulares en vidrio",
        "Ensamblador de Testeros para Fábrica de Colchones",
        "Operario de Producción - Testeros en madera",
    ],
)
def test_relevancia_no_flexiona_nombres_propios_de_tecnologia(titulo):
    """`docker` no casa en *Dockers*, ni `angular` en *angulares*, ni `tester` en *testeros*.

    Los tres son palabras españolas reales de mueblería, metalmecánica y comercio.
    Ninguno está en `sin_flexion`: los excluye la morfología, no una lista.
    """
    vocabulario = Vocabulario(
        cargos=["desarrollador", "tester"],
        tecnologias=["docker", "angular"],
    )
    assert puntuar_relevancia(_oferta(titulo), vocabulario) == 0.0


def test_la_flexion_sigue_activa_para_los_cargos_en_femenino():
    """Negar la flexión a las tecnologías no debe romper los cargos."""
    vocabulario = Vocabulario(cargos=["desarrollador", "programador"], tecnologias=["docker"])
    assert puntuar_relevancia(_oferta("Desarrolladora Backend"), vocabulario) > 0.35
    assert puntuar_relevancia(_oferta("Programadoras Python"), vocabulario) > 0.35


def test_negar_la_flexion_no_es_negar_el_termino():
    """`docker` y `tester` deben seguir casando en su forma exacta."""
    vocabulario = Vocabulario(cargos=["desarrollador", "tester"], tecnologias=["docker", "angular"])
    assert puntuar_relevancia(_oferta("Desarrollador Docker y Kubernetes"), vocabulario) > 0.35
    assert puntuar_relevancia(_oferta("Tester de Software"), vocabulario) > 0.35
    assert puntuar_relevancia(_oferta("Ingeniero Angular"), vocabulario) > 0.35


@pytest.mark.parametrize(
    "titulo",
    [
        "Conductor con manejo de App",
        "Conductores con manejo de App",
        "Conductora con manejo de App",
    ],
)
def test_sin_flexion_no_debilita_la_lista_de_excluidos(titulo):
    """`sin_flexion` no puede aplicarse a `excluidos`: ahí abre agujeros.

    Negar la flexión estrecha el emparejamiento. En una lista de inclusión eso
    reduce falsos positivos; en una de exclusión reduce las exclusiones. Con
    `conductor` en `sin_flexion`, el singular se excluía y el plural se colaba.
    """
    vocabulario = Vocabulario(
        cargos=["android"],
        excluidos=["conductor"],
        sin_flexion=["conductor"],  # se declara, pero sobre `excluidos` debe ignorarse
    )
    assert puntuar_relevancia(_oferta(titulo), vocabulario) == 0.0


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


@pytest.mark.parametrize(
    ("titulo", "debe_pasar"),
    [
        # Colisiones REALES de subcadena que la frontera debe evitar.
        # Ojo: el título NO debe contener ninguno de los términos excluidos por sí
        # mismo, o el caso se contradice — por eso "Soporte de", no "Analista de".
        ("Soporte de Directorio Activo", True),  # 'directorio' contiene 'director'
        ("Regente de Farmacia", True),  # 'regente' contiene 'gerente'
        ("Analistica de Datos", True),  # 'analistica' contiene 'analista'
        # Flexión española: SÍ deben descartarse, aunque no coincidan literalmente:
        ("Directora de Tecnología", False),
        ("Gerentes de Proyecto", False),
    ],
)
def test_experiencia_distingue_flexion_de_colision(titulo, debe_pasar):
    """La frontera debe evitar colisiones sin perder género ni plural del español."""
    cfg = ConfigExperiencia(terminos_excluidos=["director", "gerente", "analista"])
    ok, _ = experiencia_apropiada(_oferta(titulo), cfg, 60)
    assert ok is debe_pasar, titulo


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
