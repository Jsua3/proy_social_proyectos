from datetime import UTC, datetime
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


def test_dry_run_escribe_el_boletin_sin_enviar(tmp_path, monkeypatch, aislado):
    monkeypatch.setattr(
        "boletin_empleos.cli.construir_fuentes",
        lambda: [FuenteFalsa("falsa", [_oferta("f:1"), _oferta("f:2")])],
    )
    assert _correr(tmp_path, "--dry-run") == 0
    archivos = list((tmp_path / "salida").glob("*.html"))
    assert len(archivos) == 1, "el dry-run deja exactamente un HTML en disco"


def test_una_fuente_caida_no_tumba_el_boletin(tmp_path, monkeypatch, aislado):
    monkeypatch.setattr(
        "boletin_empleos.cli.construir_fuentes",
        lambda: [FuenteFalsa("viva", [_oferta("v:1", fuente="viva")]), FuenteFalsa("caida", [])],
    )
    assert _correr(tmp_path, "--dry-run") == 0
    html = next((tmp_path / "salida").glob("*.html")).read_text("utf-8")
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
        lambda args, cfg: EntregaConsola(tmp_path / "enviados"),
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
