"""De la edición al HTML. El mismo documento se lee en la web y se imprime a PDF.

El texto de `edicion.toml` nunca entra como HTML: Jinja2 escapa todo, y solo se
interpretan dos marcas, `*manuscrita*` en los títulos y `**negrita**` en los cuerpos.
"""

import re
import shutil
from enum import StrEnum
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import segno
from jinja2 import Environment, PackageLoader
from markupsafe import Markup, escape

from boletin_empleos.render.web import ESTATICOS, INSTITUCION, UNIDAD
from boletin_semestral.modelo import Edicion, antetitulo, lugar_de, pendientes

ESTATICOS_SEMESTRAL = Path(__file__).parent / "estaticos"
_LOGO = "logo-humboldt.png"
_TIPOS_CON_FOTO = {"texto", "cifras", "proyectos", "imagen"}
_MANUSCRITA = re.compile(r"\*([^*\n]+)\*")
_NEGRITA = re.compile(r"\*\*([^*\n]+)\*\*")


class Modo(StrEnum):
    BORRADOR = "borrador"
    FINAL = "final"


def manuscrita(titulo: str) -> Markup:
    """Escapa el título y pone en letra manuscrita la palabra entre asteriscos."""
    return Markup(_MANUSCRITA.sub(r'<em class="manuscrita">\1</em>', str(escape(titulo))))


def parrafos(cuerpo: str) -> Markup:
    """Un párrafo por cada bloque separado por una línea en blanco; `**x**` es negrita."""
    bloques = [b.strip() for b in re.split(r"\n\s*\n", cuerpo.strip()) if b.strip()]
    html = []
    for bloque in bloques:
        texto = _NEGRITA.sub(r"<strong>\1</strong>", str(escape(bloque)))
        html.append(f"<p>{texto.replace(chr(10), '<br>')}</p>")
    return Markup("\n".join(html))


def porcentaje(valor: float) -> str:
    """87.2 → «87,2 %», con coma decimal como se escribe en Colombia."""
    return f"{valor:.1f}".replace(".", ",") + " %"


def id_youtube(enlace: str) -> str | None:
    """El identificador de un video de YouTube, o None si el enlace es de otro sitio."""
    url = urlparse(enlace)
    anfitrion = url.netloc.lower().removeprefix("www.").removeprefix("m.")
    if anfitrion == "youtu.be":
        return url.path.strip("/") or None
    if anfitrion == "youtube.com":
        if url.path == "/watch":
            return parse_qs(url.query).get("v", [None])[0]
        for prefijo in ("/embed/", "/shorts/", "/live/"):
            if url.path.startswith(prefijo):
                return url.path.removeprefix(prefijo).strip("/") or None
    return None


def qr(enlace: str) -> Markup:
    """El código QR del enlace como SVG en línea, para la versión impresa."""
    return Markup(segno.make(enlace, error="m").svg_inline(scale=3, dark="#143D68"))


_ENTORNO = Environment(
    loader=PackageLoader("boletin_semestral", "plantillas"),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)
_ENTORNO.filters.update(
    manuscrita=manuscrita, parrafos=parrafos, porcentaje=porcentaje, id_youtube=id_youtube, qr=qr
)


def renderizar(edicion: Edicion, modo: Modo) -> str:
    """El documento HTML completo de la edición."""
    motivos = {p.lugar: p.motivo for p in pendientes(edicion)}
    secciones = [
        {
            "seccion": seccion,
            "antetitulo": antetitulo(indice, seccion),
            "pendiente": motivos.get(lugar_de(indice, seccion)),
            "falta_foto": seccion.tipo in _TIPOS_CON_FOTO and not seccion.nombres_de_fotos(),
        }
        for indice, seccion in enumerate(edicion.secciones)
    ]
    return _ENTORNO.get_template("boletin.html.j2").render(
        e=edicion,
        secciones=secciones,
        borrador=modo is Modo.BORRADOR,
        pendiente_portada=motivos.get("Portada"),
        pendiente_editorial=motivos.get("Editorial"),
        institucion=INSTITUCION,
        unidad=UNIDAD,
    )


def renderizar_plantilla(nombre: str, **contexto) -> str:
    """Renderiza otra plantilla del paquete (el índice del sitio) con los mismos filtros."""
    return _ENTORNO.get_template(nombre).render(institucion=INSTITUCION, unidad=UNIDAD, **contexto)


def copiar_estaticos(destino: Path) -> None:
    """Deja junto al HTML la hoja de estilos, el script, las fuentes y el escudo."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    for nombre in ("estilo.css", "movimiento.js"):
        shutil.copyfile(ESTATICOS_SEMESTRAL / nombre, destino / nombre)
    shutil.copytree(ESTATICOS_SEMESTRAL / "fuentes", destino / "fuentes", dirs_exist_ok=True)
    shutil.copyfile(ESTATICOS / _LOGO, destino / _LOGO)
