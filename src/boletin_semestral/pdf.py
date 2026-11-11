"""El PDF del boletín: el mismo HTML de la web, impreso en A4 con Chromium (Playwright).

Imprimir el HTML, en vez de diseñar el PDF aparte, garantiza que la web y el PDF
no se separen con el tiempo. Solo se usa en el computador del monitor: ningún
flujo de GitHub instala Chromium (spec §9).
"""

import re
from pathlib import Path
from typing import NamedTuple

from playwright.sync_api import Error, sync_playwright

INSTALAR = "uv run playwright install chromium"

# Medidas de impresión: A4 con los mismos márgenes de `@page` en estilo.css.
_MARGENES = {"top": "14mm", "right": "14mm", "bottom": "18mm", "left": "14mm"}
_PX_POR_MM = 96 / 25.4
_ANCHO_UTIL_PX = round((210 - 14 - 14) * _PX_POR_MM)
_ALTO_UTIL_PX = (297 - 14 - 18) * _PX_POR_MM

_PIE = (
    '<div style="width:100%;padding:0 14mm;display:flex;justify-content:space-between;'
    'font-family:Inter,Arial,sans-serif;font-size:7px;color:#555;">'
    "<span>Proyecci&oacute;n Social &nbsp;|&nbsp; Bolet&iacute;n Semestral</span>"
    '<span class="pageNumber"></span></div>'
)

_MEDIR_SECCIONES = f"""() => [...document.querySelectorAll('.pagina.seccion')].map(
    s => [s.dataset.titulo, Math.ceil(s.offsetHeight / {_ALTO_UTIL_PX})]
)"""


class ChromiumAusente(Exception):
    """Falta el navegador con el que se imprime el PDF."""


class ResultadoPdf(NamedTuple):
    paginas: int
    largas: list[tuple[str, int]]


def generar_pdf(html: Path, destino: Path) -> ResultadoPdf:
    """Imprime el HTML a PDF y avisa qué secciones ocupan más de una página."""
    with sync_playwright() as p:
        try:
            navegador = p.chromium.launch()
        except Error as e:
            if "Executable doesn't exist" in str(e):
                raise ChromiumAusente(
                    f"Falta el navegador con el que se genera el PDF. Instálalo una sola vez con: "
                    f"{INSTALAR}"
                ) from None
            raise
        try:
            pagina = navegador.new_page(viewport={"width": _ANCHO_UTIL_PX, "height": 1000})
            pagina.goto(Path(html).resolve().as_uri())
            pagina.wait_for_load_state("networkidle")
            pagina.evaluate("document.fonts.ready")
            pagina.emulate_media(media="print")
            largas = [(titulo, n) for titulo, n in pagina.evaluate(_MEDIR_SECCIONES) if n > 1]
            pagina.pdf(
                path=str(destino),
                format="A4",
                print_background=True,
                margin=_MARGENES,
                display_header_footer=True,
                header_template="<span></span>",
                footer_template=_PIE,
            )
        finally:
            navegador.close()

    paginas = len(re.findall(rb"/Type\s*/Page[^s]", Path(destino).read_bytes()))
    return ResultadoPdf(paginas=paginas, largas=largas)
