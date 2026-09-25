from datetime import UTC, datetime
from pathlib import Path

import pytest

from boletin_empleos.config import cargar_config
from boletin_empleos.modelos import Modalidad, Oferta
from boletin_empleos.nucleo.experiencia import experiencia_apropiada
from boletin_empleos.nucleo.geografia import es_del_eje_cafetero
from boletin_empleos.nucleo.relevancia import puntuar_relevancia

RAIZ = Path(__file__).resolve().parents[1]


def test_carga_el_config_del_proyecto():
    cfg = cargar_config(RAIZ / "programas" / "software.toml")

    assert cfg.destinatarios, "debe haber al menos un destinatario"
    assert cfg.vocabulario.cargos, "el vocabulario de cargos no puede estar vacío"
    assert cfg.vocabulario.tecnologias
    assert 0.0 < cfg.umbral_relevancia <= 1.0
    assert cfg.dias_max_antiguedad > 0
    assert cfg.legitimidad.frases_descarte
    assert cfg.legitimidad.min_caracteres_descripcion == 200


def test_los_terminos_del_vocabulario_estan_normalizados():
    cfg = cargar_config(RAIZ / "programas" / "software.toml")
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
    cfg = cargar_config(RAIZ / "programas" / "software.toml")
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
    cfg = cargar_config(RAIZ / "programas" / "software.toml")
    assert _pasa_relevancia_y_experiencia(cfg, titulo, descripcion) is True, titulo


def test_r2_3_sr_reemplaza_a_sr_punto_sin_perder_cobertura_ni_casar_en_sres():
    """ "sr." pasó a "sr": la frontera de palabra ya cubre "Sr" y "Sr." sin el

    punto, y "sr" no debe casar dentro de "Sres."."""
    cfg = cargar_config(RAIZ / "programas" / "software.toml")
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


def test_r2_3_desarrollador_a_comercial_con_barra_tambien_queda_fuera():
    """Encontrado en la corrida real de esta ronda (no solo en el registro del

    primer boletín): "Desarrollador/a comercial" pasó pese al término
    "desarrollador comercial" — la barra de género neutro ("/a") rompe la
    coincidencia exacta de la frase, y el título por sí solo ya suma
    relevancia vía el cargo "desarrollador". Se cubre con el propio título
    real como término adicional en `excluidos`."""
    cfg = cargar_config(RAIZ / "programas" / "software.toml")
    assert puntuar_relevancia(_oferta("Desarrollador/a comercial"), cfg.vocabulario) == 0.0


def test_el_config_del_proyecto_apunta_al_sitio_publico():
    """Sin url_base el correo llevaría el boletín entero y Gmail lo recortaría."""
    cfg = cargar_config(RAIZ / "programas" / "software.toml")

    assert cfg.sitio.url_base.startswith("https://")
    assert cfg.sitio.vacantes_en_correo > 0


def test_sin_seccion_sitio_no_hay_enlace_y_el_correo_va_completo(tmp_path):
    ruta = tmp_path / "config.toml"
    ruta.write_text(
        'clave = "x"\n'
        'programa = "Programa de prueba"\n'
        'destinatarios = ["a@b.co"]\n'
        'remitente = "a@b.co"\n'
        'asunto = "Boletín"\n'
        "umbral_relevancia = 0.35\n"
        "dias_max_antiguedad = 30\n",
        encoding="utf-8",
    )

    cfg = cargar_config(ruta)

    assert cfg.sitio.url_base == ""
    assert cfg.sitio.vacantes_en_correo == 10


@pytest.mark.parametrize(
    "ubicacion, esperado",
    [
        # Tal como las escribe el SPE, verificado contra su API el 20/09/2026.
        ("ARMENIA, QUI, QUINDIO", True),
        ("PEREIRA, RISARALDA", True),
        ("DOSQUEBRADAS, RISARALDA", True),
        ("MANIZALES, CALDAS", True),
        ("CHINCHINÁ, CALDAS", True),
        ("MEDELLÍN, ANTIOQUIA", False),
        ("BOGOTÁ, D.C., BOGOTÁ, D.C.", False),
        ("CALI, VALLE DEL CAUCA", False),
    ],
)
def test_la_geografia_del_proyecto_reconoce_el_eje_cafetero(ubicacion, esperado):
    cfg = cargar_config(RAIZ / "programas" / "software.toml")

    assert es_del_eje_cafetero(ubicacion, cfg.geografia) is esperado


# --- Dos carreras, una sola base ------------------------------------------------


def _escribir(ruta, texto):
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def test_un_programa_extiende_la_configuracion_comun(tmp_path):
    _escribir(
        tmp_path / "comun.toml",
        "dias_max_antiguedad = 30\numbral_relevancia = 0.35\n"
        '[geografia]\ndepartamentos = ["quindio"]\n',
    )
    _escribir(
        tmp_path / "x.toml",
        'extiende = "comun.toml"\nclave = "x"\nprograma = "Programa de prueba"\n'
        'destinatarios = ["a@b.co"]\nremitente = "a@b.co"\nasunto = "A"\n'
        '[vocabulario]\ncargos = ["ingeniero"]\n',
    )

    cfg = cargar_config(tmp_path / "x.toml")

    assert cfg.dias_max_antiguedad == 30, "heredado de la base"
    assert cfg.geografia.departamentos == ["quindio"], "la geografía es común a las carreras"
    assert cfg.vocabulario.cargos == ["ingeniero"], "el vocabulario es propio"
    assert cfg.programa == "Programa de prueba"
    assert cfg.clave == "x"


def test_lo_que_define_el_programa_manda_sobre_lo_comun(tmp_path):
    _escribir(tmp_path / "comun.toml", "dias_max_antiguedad = 30\numbral_relevancia = 0.35\n")
    _escribir(
        tmp_path / "x.toml",
        'extiende = "comun.toml"\nclave = "x"\nprograma = "P"\numbral_relevancia = 0.5\n'
        'destinatarios = ["a@b.co"]\nremitente = "a@b.co"\nasunto = "A"\n',
    )

    cfg = cargar_config(tmp_path / "x.toml")

    assert cfg.umbral_relevancia == 0.5
    assert cfg.dias_max_antiguedad == 30


def test_las_dos_carreras_reales_comparten_base_y_difieren_en_vocabulario():
    software = cargar_config(RAIZ / "programas" / "software.toml")
    industrial = cargar_config(RAIZ / "programas" / "industrial.toml")

    assert (software.clave, industrial.clave) == ("software", "industrial")
    assert "Software" in software.programa and "Industrial" in industrial.programa
    assert software.geografia.departamentos == industrial.geografia.departamentos
    assert software.legitimidad.frases_descarte == industrial.legitimidad.frases_descarte
    assert software.vocabulario.cargos != industrial.vocabulario.cargos
    assert software.destinatarios == industrial.destinatarios, "misma Coordinación"
    assert software.asunto != industrial.asunto, "el asunto dice de qué carrera es"


def test_cada_carrera_consulta_sus_propios_cargos_en_las_fuentes():
    software = cargar_config(RAIZ / "programas" / "software.toml")
    industrial = cargar_config(RAIZ / "programas" / "industrial.toml")

    cargos_software = [c.get("cargo", "") for c in software.fuentes.consultas()]
    cargos_industrial = [c.get("cargo", "") for c in industrial.fuentes.consultas()]

    assert any("desarrollador" in c for c in cargos_software)
    assert any("industrial" in c for c in cargos_industrial)
    assert software.fuentes.rutas_magneto, "las rutas de Magneto también salen de la configuración"


# --- Fugas medidas en la primera corrida real de Industrial (22/09/2026) --------

_FUGAS_INDUSTRIAL = [
    "Analista de Nomina SAP HCM [Remoto] - Bogota",
    "Lider de Nomina SAP (SAP HCM) [Hibrido]",
    "Gestor de novedades - Nomina SAP",
    "Analista de seguridad social - Nomina - SAP",
    "Auxiliar contable - sap - facturacion electronica - bogota",
    "Desarrollador SAP ABAP y Funcional [Hibrido]",
    "Consultor SAP FSCM o Consultor SAP TM Remoto",
    "Analista de planeacion financiera para personas con o sin discapacidad",
]

_LEGITIMAS_INDUSTRIAL = [
    "Ingeniero Industrial",
    "Analista de inventarios",
    "Coordinador de Produccion",
    "Supervisor de produccion",
    "Profesional en seguridad y salud en el trabajo",
    "Analista de costos",
    "Auditor de Calidad (ISO/IEC 17025)",
]


def _pasa_relevancia(titulo: str, cfg) -> bool:
    oferta = Oferta(
        id="x:1",
        fuente="spe",
        titulo=titulo,
        modalidad=Modalidad.PRESENCIAL,
        url="https://ejemplo.co/1",
        descripcion="Empresa del sector busca profesional para el cargo descrito. " * 5,
        recogida_en=datetime(2026, 9, 22, tzinfo=UTC),
    )
    puntaje = puntuar_relevancia(oferta, cfg.vocabulario, cfg.relevancia)
    return puntaje >= cfg.umbral_relevancia


@pytest.mark.parametrize("titulo", _FUGAS_INDUSTRIAL)
def test_las_fugas_de_nomina_y_software_no_entran_al_boletin_de_industrial(titulo):
    """«SAP» a secas alcanzaba para colar nóminas, contabilidad y desarrollo."""
    cfg = cargar_config(RAIZ / "programas" / "industrial.toml")

    assert not _pasa_relevancia(titulo, cfg), titulo


@pytest.mark.parametrize("titulo", _LEGITIMAS_INDUSTRIAL)
def test_las_vacantes_propias_de_industrial_siguen_entrando(titulo):
    cfg = cargar_config(RAIZ / "programas" / "industrial.toml")

    assert _pasa_relevancia(titulo, cfg), titulo


# --- Profesiones ajenas: medido sobre el boletín del 22/09/2026 -----------------
# La profesora encontró una vacante de enfermería en el boletín de Industrial.
# Al revisar la edición aparecieron trece del sector salud; estas piden una
# profesión que nuestros egresados no tienen, y estas otras son trabajo de
# ingeniería industrial en una empresa del sector, que sí les sirve.

_PIDEN_OTRA_PROFESION = [
    "Auxiliar de Enfermería Profesional en Seguridad y Salud en el Trabajo - Pereira",
    "Analista de Calidad - Regente de farmacia, Pereira",
    "Analista de compras - (Regente de farmacia)",
    "coordinador de calidad - Quimico farmaceutico",
    "coordinador de produccion - químico farmacéutico",
    "Auditor de calidad - área de odontología",
    "Auditor de calidad - Clinica Odontologica",
    "Analista de Calidad Y Resolucion QRS -Abogado",
]

_SON_DEL_SECTOR_PERO_SIRVEN = [
    "Analista de compras - Sector salud o farmacéutico",
    "Analista de Compras - Sector farmaceutico",
    "Analista de Inventarios - Sector Farmacéutico",
    "Analista de inventarios - Salud o farmacéutico",
]


@pytest.mark.parametrize("titulo", _PIDEN_OTRA_PROFESION)
def test_las_vacantes_que_piden_otra_profesion_quedan_fuera(titulo):
    cfg = cargar_config(RAIZ / "programas" / "industrial.toml")

    assert not _pasa_relevancia(titulo, cfg), titulo


@pytest.mark.parametrize("titulo", _SON_DEL_SECTOR_PERO_SIRVEN)
def test_trabajar_en_el_sector_salud_no_descalifica_la_vacante(titulo):
    """El sector no es la profesión: comprar insumos para una farmacéutica es

    trabajo de ingeniería industrial."""
    cfg = cargar_config(RAIZ / "programas" / "industrial.toml")

    assert _pasa_relevancia(titulo, cfg), titulo


# --- Datos e IA: destino habitual de los egresados de software -----------------
# El portal que recomendó la profesora publica sobre todo vacantes de datos e
# inteligencia artificial, y el vocabulario no las reconocía: de ocho vacantes
# suyas solo entraba una.

_VACANTES_DE_DATOS = [
    "Data Scientist with Gen AI experience",
    "Científico de Datos Junior",
    "Analista de datos",
    "Ingeniero de Machine Learning",
    "Desarrollador de Inteligencia Artificial",
    "Analista de Business Intelligence",
    "Ingeniero de Ciberseguridad",
]

_NO_SON_DE_SOFTWARE = [
    "Analista de laboratorio de datos clínicos",
    "Asesor comercial de soluciones de datos",
]


@pytest.mark.parametrize("titulo", _VACANTES_DE_DATOS)
def test_las_vacantes_de_datos_e_ia_entran_al_boletin_de_software(titulo):
    cfg = cargar_config(RAIZ / "programas" / "software.toml")

    assert _pasa_relevancia(titulo, cfg), titulo


@pytest.mark.parametrize("titulo", _NO_SON_DE_SOFTWARE)
def test_ampliar_a_datos_no_abre_la_puerta_a_cualquier_cosa(titulo):
    cfg = cargar_config(RAIZ / "programas" / "software.toml")

    assert not _pasa_relevancia(titulo, cfg), titulo
