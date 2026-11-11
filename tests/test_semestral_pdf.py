"""El PDF sale del mismo HTML impreso con Chromium; sin Chromium, dice cómo instalarlo."""

import shutil
from contextlib import contextmanager

import pytest
from conftest import leer_datos
from playwright.sync_api import Error, sync_playwright

from boletin_semestral import pdf
from boletin_semestral.edicion import cargar
from boletin_semestral.modelo import Edicion
from boletin_semestral.pdf import ChromiumAusente, generar_pdf
from boletin_semestral.render import Modo, copiar_estaticos, renderizar


def _chromium_o_saltar():
    try:
        with sync_playwright() as p:
            p.chromium.launch().close()
    except Error:
        pytest.skip("Chromium no instalado (uv run playwright install chromium)")


def _escribir(edicion: Edicion, carpeta_edicion, destino):
    destino.mkdir(parents=True)
    (destino / "index.html").write_text(renderizar(edicion, Modo.FINAL), encoding="utf-8")
    copiar_estaticos(destino)
    shutil.copytree(carpeta_edicion / "fotos", destino / "fotos")
    return destino / "index.html"


def test_pdf_de_una_edicion_minima(carpeta_edicion, tmp_path):
    _chromium_o_saltar()
    html = _escribir(cargar(carpeta_edicion), carpeta_edicion, tmp_path / "salida")

    resultado = generar_pdf(html, tmp_path / "boletin.pdf")

    assert (tmp_path / "boletin.pdf").read_bytes().startswith(b"%PDF")
    assert resultado.paginas >= 9
    assert resultado.largas == []


def test_seccion_larga_se_avisa(carpeta_edicion, tmp_path):
    _chromium_o_saltar()
    datos = leer_datos(carpeta_edicion)
    datos["secciones"][1]["cuerpo"] = "\n\n".join(
        ["Un párrafo largo sobre la jornada de siembra y sus participantes. " * 4] * 60
    )
    html = _escribir(Edicion.model_validate(datos), carpeta_edicion, tmp_path / "salida")

    resultado = generar_pdf(html, tmp_path / "boletin.pdf")

    titulos = {titulo: paginas for titulo, paginas in resultado.largas}
    assert titulos.get("Nuestro compromiso con el planeta", 0) >= 2


def test_sin_chromium_da_el_comando(monkeypatch, tmp_path):
    class _ChromiumAusente:
        def launch(self):
            raise Error("BrowserType.launch: Executable doesn't exist at C:\\x\\chrome.exe")

    class _Playwright:
        chromium = _ChromiumAusente()

    @contextmanager
    def _falso():
        yield _Playwright()

    monkeypatch.setattr(pdf, "sync_playwright", _falso)
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")

    with pytest.raises(ChromiumAusente, match="uv run playwright install chromium"):
        generar_pdf(tmp_path / "index.html", tmp_path / "boletin.pdf")
