from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from boletin_empleos.cli import main
from boletin_empleos.entrega.consola import EntregaConsola
from boletin_empleos.modelos import Modalidad, Oferta

# Ruta absoluta: los tests no dependen del directorio desde el que se lance pytest.
CONFIG = Path(__file__).resolve().parents[1] / "config.toml"


class FuenteFalsa:
    def __init__(self, nombre, ofertas, confianza=0.9):
        self.nombre = nombre
        self.base_permiso = "prueba"
        self.atribucion = f"Ofertas de {nombre}."
        self.url_atribucion = f"https://{nombre}.ejemplo.co/"
        self.confianza_base = confianza
        self._ofertas = ofertas

    def obtener(self):
        return self._ofertas


def _oferta(id_, fuente="falsa", titulo="Desarrollador Backend Python"):
    # `fuente` debe coincidir con el nombre de la FuenteFalsa que la aporta: el pipeline
    # busca la confianza base por ese nombre y, si no la encuentra, usa un valor por defecto.
    return Oferta(
        id=id_,
        fuente=fuente,
        titulo=titulo,
        empresa="Acme S.A.S.",
        ubicacion="Armenia, Quindío",
        pais="CO",
        modalidad=Modalidad.PRESENCIAL,
        url=f"https://ejemplo.co/{id_}",
        descripcion="Buscamos desarrollador con Python. " * 10,
        recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
    )


@pytest.fixture
def aislado(monkeypatch):
    """Sin red y sin LLM: ni verificación de enlaces ni llamadas a la API de Anthropic.

    Sin el `delenv`, quien corra la suite con ANTHROPIC_API_KEY en su entorno haría
    llamadas reales, y pagadas, en cada ejecución de los tests.
    """
    monkeypatch.setattr("boletin_empleos.cli.filtrar_enlaces_vivos", lambda evs: (evs, []))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _correr(tmp_path, *extra):
    return main(
        [
            *extra,
            "--config",
            str(CONFIG),
            "--salida",
            str(tmp_path / "salida"),
            "--historial",
            str(tmp_path / "h.json"),
        ]
    )


def test_dry_run_deja_la_edicion_completa_y_la_vista_previa_del_correo(
    tmp_path, monkeypatch, aislado
):
    """La edición se escribe también en vista previa: es lo que publica el sitio.

    El historial sigue intacto, que es la invariante que importa: una vista previa
    no puede dar por enviadas las ofertas que la directora todavía no ha recibido.
    """
    monkeypatch.setattr(
        "boletin_empleos.cli.construir_fuentes",
        lambda: [FuenteFalsa("falsa", [_oferta("f:1"), _oferta("f:2")])],
    )
    assert _correr(tmp_path, "--dry-run") == 0

    hoy = date.today().isoformat()
    salida = tmp_path / "salida"
    assert (salida / f"{hoy}.html").exists(), "la edición completa, la que se publica"
    assert (salida / f"{hoy}-correo.html").exists(), "lo que recibiría la directora"
    assert not (tmp_path / "h.json").exists()


def test_el_correo_enlaza_la_edicion_publicada_y_la_edicion_no(tmp_path, monkeypatch, aislado):
    monkeypatch.setattr(
        "boletin_empleos.cli.construir_fuentes",
        lambda: [FuenteFalsa("falsa", [_oferta("f:1"), _oferta("f:2")])],
    )
    assert _correr(tmp_path, "--dry-run") == 0

    hoy = date.today().isoformat()
    salida = tmp_path / "salida"
    enlace = f"/ediciones/{hoy}.html"
    assert enlace in (salida / f"{hoy}-correo.html").read_text("utf-8")
    assert enlace not in (salida / f"{hoy}.html").read_text("utf-8"), (
        "la edición de la web no se enlaza a sí misma"
    )


def test_una_fuente_caida_no_tumba_el_boletin(tmp_path, monkeypatch, aislado):
    monkeypatch.setattr(
        "boletin_empleos.cli.construir_fuentes",
        lambda: [FuenteFalsa("viva", [_oferta("v:1", fuente="viva")]), FuenteFalsa("caida", [])],
    )
    assert _correr(tmp_path, "--dry-run") == 0
    html = (tmp_path / "salida" / f"{date.today().isoformat()}.html").read_text("utf-8")
    assert "caida" in html and "no respondió" in html


def test_sin_ninguna_oferta_no_se_envia_boletin(tmp_path, monkeypatch, aislado):
    monkeypatch.setattr("boletin_empleos.cli.construir_fuentes", lambda: [FuenteFalsa("caida", [])])
    assert _correr(tmp_path, "--dry-run") == 2, "sin fuentes vivas no se envía boletín vacío"
    assert not list((tmp_path / "salida").glob("*.html"))


def test_el_historial_evita_repetir_ofertas(tmp_path, monkeypatch, aislado):
    monkeypatch.setattr(
        "boletin_empleos.cli.construir_fuentes",
        lambda: [FuenteFalsa("falsa", [_oferta("f:1")])],
    )
    # Envío real simulado: la entrega escribe en disco en vez de usar SMTP.
    monkeypatch.setattr(
        "boletin_empleos.cli._crear_entrega",
        lambda args, cfg, hoy: EntregaConsola(tmp_path / "enviados"),
    )
    assert _correr(tmp_path) == 0
    # Segunda corrida: la misma oferta ya fue enviada, no quedan nuevas.
    assert _correr(tmp_path) == 3


def test_dry_run_no_consume_las_ofertas_de_la_edicion_real(tmp_path, monkeypatch, aislado):
    """Un dry-run es una vista previa.

    Si registrara el historial, las ofertas que la coordinación revisó en la prueba
    nunca llegarían en la edición real (spec §15, criterio 4).
    """
    monkeypatch.setattr(
        "boletin_empleos.cli.construir_fuentes",
        lambda: [FuenteFalsa("falsa", [_oferta("f:1")])],
    )
    assert _correr(tmp_path, "--dry-run") == 0
    assert _correr(tmp_path, "--dry-run") == 0, "la segunda vista previa ve la misma oferta"
    assert not (tmp_path / "h.json").exists()


def test_sin_credenciales_smtp_no_envia_ni_registra(tmp_path, monkeypatch, aislado):
    monkeypatch.setattr(
        "boletin_empleos.cli.construir_fuentes",
        lambda: [FuenteFalsa("falsa", [_oferta("f:1")])],
    )
    for variable in ("SMTP_HOST", "SMTP_USUARIO", "SMTP_CLAVE"):
        monkeypatch.delenv(variable, raising=False)
    assert _correr(tmp_path) == 1
    assert not (tmp_path / "h.json").exists()


def test_sin_credenciales_smtp_no_consulta_fuentes_ni_ia(tmp_path, monkeypatch, aislado):
    """T15-1: la entrega se valida antes de recolectar — nunca se paga por nada."""
    llamadas = []

    def _fuentes_que_registran_la_llamada():
        llamadas.append(True)
        return [FuenteFalsa("falsa", [_oferta("f:1")])]

    monkeypatch.setattr("boletin_empleos.cli.construir_fuentes", _fuentes_que_registran_la_llamada)
    for variable in ("SMTP_HOST", "SMTP_USUARIO", "SMTP_CLAVE"):
        monkeypatch.delenv(variable, raising=False)
    assert _correr(tmp_path) == 1
    assert not llamadas, "sin credenciales SMTP no se debe consultar ninguna fuente"
    assert not (tmp_path / "h.json").exists()


def test_config_inexistente_devuelve_1(tmp_path):
    assert (
        main(
            [
                "--config",
                str(tmp_path / "no-existe.toml"),
                "--dry-run",
                "--salida",
                str(tmp_path / "salida"),
                "--historial",
                str(tmp_path / "h.json"),
            ]
        )
        == 1
    )


def test_config_con_toml_invalido_devuelve_1(tmp_path):
    config_mala = tmp_path / "config.toml"
    config_mala.write_text("esto no es toml válido [[[\n", encoding="utf-8")
    assert (
        main(
            [
                "--config",
                str(config_mala),
                "--dry-run",
                "--salida",
                str(tmp_path / "salida"),
                "--historial",
                str(tmp_path / "h.json"),
            ]
        )
        == 1
    )


def test_config_con_campo_obligatorio_ausente_devuelve_1(tmp_path):
    config_incompleta = tmp_path / "config.toml"
    config_incompleta.write_text("", encoding="utf-8")  # faltan todos los campos obligatorios
    assert (
        main(
            [
                "--config",
                str(config_incompleta),
                "--dry-run",
                "--salida",
                str(tmp_path / "salida"),
                "--historial",
                str(tmp_path / "h.json"),
            ]
        )
        == 1
    )


def _renderizar_que_falla(datos):
    raise ValueError("fallo simulado de render")


def test_fallo_de_render_devuelve_1_y_no_registra_historial(tmp_path, monkeypatch, aislado):
    monkeypatch.setattr(
        "boletin_empleos.cli.construir_fuentes",
        lambda: [FuenteFalsa("falsa", [_oferta("f:1")])],
    )
    # Entrega real simulada (sin SMTP) para que el fallo bajo prueba sea el del render.
    monkeypatch.setattr(
        "boletin_empleos.cli._crear_entrega",
        lambda args, cfg, hoy: EntregaConsola(tmp_path / "enviados"),
    )
    monkeypatch.setattr("boletin_empleos.cli.renderizar", _renderizar_que_falla)
    assert _correr(tmp_path) == 1
    assert not (tmp_path / "h.json").exists()


def test_historial_corrupto_devuelve_1_y_no_consulta_fuentes(tmp_path, monkeypatch, aislado):
    historial_malo = tmp_path / "h.json"
    historial_malo.write_text("esto no es json {", encoding="utf-8")
    llamadas = []

    def _fuentes_que_registran_la_llamada():
        llamadas.append(True)
        return []

    monkeypatch.setattr("boletin_empleos.cli.construir_fuentes", _fuentes_que_registran_la_llamada)
    assert (
        main(
            [
                "--dry-run",
                "--config",
                str(CONFIG),
                "--salida",
                str(tmp_path / "salida"),
                "--historial",
                str(historial_malo),
            ]
        )
        == 1
    )
    assert not llamadas, "un historial ilegible no debe llegar a consultar fuentes"


class _EntregaQueFalla:
    def enviar(self, asunto, html, destinatarios):
        return False


def test_entrega_que_falla_en_modo_real_devuelve_1_y_no_registra_historial(
    tmp_path, monkeypatch, aislado
):
    monkeypatch.setattr(
        "boletin_empleos.cli.construir_fuentes",
        lambda: [FuenteFalsa("falsa", [_oferta("f:1")])],
    )
    monkeypatch.setattr(
        "boletin_empleos.cli._crear_entrega", lambda args, cfg, hoy: _EntregaQueFalla()
    )
    assert _correr(tmp_path) == 1
    assert not (tmp_path / "h.json").exists()


def test_argumento_invalido_sale_con_codigo_1():
    with pytest.raises(SystemExit) as excinfo:
        main(["--flag-que-no-existe"])
    assert excinfo.value.code == 1


def test_la_edicion_que_se_publica_es_la_pagina_web_y_el_correo_sigue_siendo_correo(
    tmp_path, monkeypatch, aislado
):
    """Dos piezas distintas: la web puede usar la identidad completa; el correo no."""
    monkeypatch.setattr(
        "boletin_empleos.cli.construir_fuentes",
        lambda: [FuenteFalsa("falsa", [_oferta("f:1")])],
    )
    assert _correr(tmp_path, "--dry-run") == 0

    hoy = date.today().isoformat()
    edicion = (tmp_path / "salida" / f"{hoy}.html").read_text("utf-8")
    correo = (tmp_path / "salida" / f"{hoy}-correo.html").read_text("utf-8")

    assert "estilo.css" in edicion, "la edición es la página del sitio"
    assert "logo-humboldt" in edicion
    assert "estilo.css" not in correo, "el correo no puede depender de una hoja externa"
    assert "logo-humboldt" in correo, "pero sí lleva el escudo, servido desde el sitio"
