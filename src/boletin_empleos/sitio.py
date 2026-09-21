"""Sitio público: el archivo histórico de ediciones.

El correo a la Coordinación solo lleva las vacantes más pertinentes, porque Gmail
recorta los mensajes de más de unos 102 KB. La edición completa se publica aquí y
el correo la enlaza. De paso, una lista de ediciones fechadas es el rastro que el
CNA pide para el seguimiento a la empleabilidad (Acuerdo 01 de 2025, Factor 12).

Toca disco, no red: por eso vive fuera del núcleo.
"""

import argparse
import json
import logging
import re
import shutil
from datetime import date
from html import escape
from pathlib import Path

from boletin_empleos.render.formato import en_palabras
from boletin_empleos.render.web import (
    ARCHIVOS_ESTATICOS,
    ESTATICOS,
    INSTITUCION,
    UNIDAD,
    pagina,
)

_log = logging.getLogger(__name__)

# Solo `AAAA-MM-DD.html` es una edición. En la misma carpeta pueden quedar otros
# archivos: el dry-run deja además la vista previa del correo.
_NOMBRE_EDICION = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")


def construir_sitio(ediciones: Path, destino: Path, historial: Path | None = None) -> list[date]:
    """Copia las ediciones al sitio y escribe el índice. Devuelve las publicadas."""
    fechas = sorted(_ediciones(Path(ediciones)), reverse=True)
    enviadas = _fechas_enviadas(historial)

    destino = Path(destino)
    (destino / "ediciones").mkdir(parents=True, exist_ok=True)

    vacantes: dict[date, int] = {}
    for fecha in fechas:
        nombre = f"{fecha.isoformat()}.html"
        origen = Path(ediciones) / nombre
        shutil.copyfile(origen, destino / "ediciones" / nombre)
        vacantes[fecha] = _vacantes_en(origen)

    # Hoja de estilos, escudo y movimiento: sin ellos la página se ve desnuda.
    for estatico in ARCHIVOS_ESTATICOS:
        shutil.copyfile(ESTATICOS / estatico, destino / estatico)

    (destino / "index.html").write_text(_indice(fechas, enviadas, vacantes), encoding="utf-8")
    _log.info("sitio construido en %s con %d ediciones", destino, len(fechas))
    return fechas


def _ediciones(directorio: Path) -> list[date]:
    if not directorio.is_dir():
        return []

    fechas = []
    for archivo in directorio.glob("*.html"):
        coincidencia = _NOMBRE_EDICION.match(archivo.name)
        if not coincidencia:
            continue
        try:
            fechas.append(date.fromisoformat(coincidencia.group(1)))
        except ValueError:
            _log.warning("nombre de edición con fecha imposible: %s", archivo.name)
    return fechas


def _fechas_enviadas(historial: Path | None) -> set[date]:
    """Un historial ausente o ilegible no puede tumbar la publicación del sitio."""
    if historial is None or not Path(historial).exists():
        return set()
    try:
        datos = json.loads(Path(historial).read_text("utf-8"))
        return {date.fromisoformat(e["fecha"]) for e in datos.get("ediciones", [])}
    except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError) as e:
        _log.warning("historial ilegible en %s (%s); el sitio no marcará envíos", historial, e)
        return set()


def _vacantes_en(archivo: Path) -> int:
    """Cuántas vacantes trae una edición: un botón «Ver oferta» por vacante."""
    try:
        return archivo.read_text("utf-8").count(">Ver oferta</a>")
    except OSError as e:
        _log.warning("no se pudo leer %s para contar vacantes (%s)", archivo, e)
        return 0


def _tarjeta(fecha: date, enviada: bool, vacantes: int) -> str:
    estado = "Enviada a la Coordinación" if enviada else "Vista previa"
    clase = "enviada" if enviada else "previa"
    detalle = f"{vacantes} vacantes" if vacantes else "Edición completa"
    return (
        f'      <li><a class="edicion" href="ediciones/{fecha.isoformat()}.html">\n'
        f"        <span>\n"
        f'          <span class="edicion__fecha">{escape(en_palabras(fecha))}</span><br>\n'
        f'          <span class="edicion__detalle">{detalle}</span>\n'
        f"        </span>\n"
        f'        <span class="insignia insignia--{clase}">{estado}</span>\n'
        f'        <span class="edicion__flecha" aria-hidden="true">›</span>\n'
        f"      </a></li>"
    )


def _indice(fechas: list[date], enviadas: set[date], vacantes: dict[date, int]) -> str:
    if fechas:
        tarjetas = "\n".join(_tarjeta(f, f in enviadas, vacantes.get(f, 0)) for f in fechas)
        lista = f'    <ul class="ediciones">\n{tarjetas}\n    </ul>'
    else:
        lista = '    <p class="aviso">Todavía no hay ediciones publicadas.</p>'

    # La portada va sin párrafo: el título ya dice qué hay, y la explicación del
    # proceso vive en el pie, donde no estorba.
    cuerpo = f"""  <section class="portada aparece">
    <span class="etiqueta">Boletín quincenal</span>
    <h1>Vacantes de software para nuestros egresados</h1>
  </section>

  <section class="seccion aparece">
{lista}
  </section>

  <footer class="pie aparece">
    <p><strong>{escape(UNIDAD)}</strong><br>{escape(INSTITUCION)} · Armenia, Quindío</p>
    <p>
      Vacantes recogidas del Servicio Público de Empleo, Magneto365, Remotive y Remote OK,
      fuentes que autorizan expresamente su uso. Cada edición cita a las que aportaron ofertas.
    </p>
  </footer>"""

    return pagina(
        titulo="Boletín de empleos — Ingeniería de Software",
        descripcion=(
            "Archivo de ediciones del boletín quincenal de empleos para egresados de "
            "Ingeniería de Software de la Corporación Universitaria Empresarial "
            "Alexander von Humboldt."
        ),
        cuerpo=cuerpo,
    )


def main(argv: list[str] | None = None) -> int:
    """Entrada para el workflow: `python -m boletin_empleos.sitio`."""
    p = argparse.ArgumentParser(prog="sitio", description="Construye el sitio de ediciones")
    p.add_argument("--ediciones", type=Path, default=Path("datos/ediciones"))
    p.add_argument("--destino", type=Path, default=Path("sitio"))
    p.add_argument("--historial", type=Path, default=Path("datos/historial.json"))
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    publicadas = construir_sitio(args.ediciones, args.destino, args.historial)
    _log.info("%d ediciones publicadas en %s", len(publicadas), args.destino)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
