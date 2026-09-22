"""Sitio público: el archivo histórico de ediciones, carrera por carrera.

El correo a la Coordinación solo lleva las vacantes más pertinentes, porque Gmail
recorta los mensajes de más de unos 102 KB. La edición completa se publica aquí y
el correo la enlaza. De paso, una lista de ediciones fechadas es el rastro que el
CNA pide para el seguimiento a la empleabilidad (Acuerdo 01 de 2025, Factor 12).

Estructura publicada:

    index.html                       portada con las carreras
    estilo.css · logo · movimiento   compartidos por todas
    <clave>/index.html               ediciones de esa carrera
    <clave>/ediciones/AAAA-MM-DD.html

Toca disco, no red: por eso vive fuera del núcleo.
"""

import argparse
import json
import logging
import re
import shutil
import tomllib
from datetime import date
from html import escape
from pathlib import Path

from pydantic import BaseModel

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


class ProgramaSitio(BaseModel):
    """Una carrera y dónde están sus cosas."""

    clave: str
    programa: str
    ediciones: Path
    historial: Path | None = None


def programas_desde(carpeta: Path, datos: Path) -> list[ProgramaSitio]:
    """Descubre las carreras leyendo programas/*.toml.

    Añadir una carrera nueva es dejar caer su archivo ahí: ni el sitio ni el
    workflow necesitan enterarse.
    """
    programas = []
    for archivo in sorted(Path(carpeta).glob("*.toml")):
        with archivo.open("rb") as f:
            cfg = tomllib.load(f)
        clave, nombre = cfg.get("clave"), cfg.get("programa")
        if not clave or not nombre:
            continue  # comun.toml y cualquier otro archivo de apoyo
        programas.append(
            ProgramaSitio(
                clave=clave,
                programa=nombre,
                ediciones=Path(datos) / clave / "ediciones",
                historial=Path(datos) / clave / "historial.json",
            )
        )
    return programas


def construir_sitio(programas: list[ProgramaSitio], destino: Path) -> dict[str, list[date]]:
    """Publica el sitio entero. Devuelve, por carrera, las ediciones publicadas."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)

    # Hoja de estilos, escudo y movimiento: una sola copia para todas las carreras.
    for estatico in ARCHIVOS_ESTATICOS:
        shutil.copyfile(ESTATICOS / estatico, destino / estatico)

    publicadas: dict[str, list[date]] = {}
    resumen: list[tuple[ProgramaSitio, list[date]]] = []
    for programa in programas:
        fechas = _publicar_carrera(programa, destino)
        publicadas[programa.clave] = fechas
        resumen.append((programa, fechas))

    (destino / "index.html").write_text(_portada(resumen), encoding="utf-8")
    _log.info(
        "sitio construido en %s con %d carreras y %d ediciones",
        destino,
        len(programas),
        sum(len(f) for f in publicadas.values()),
    )
    return publicadas


def _publicar_carrera(programa: ProgramaSitio, destino: Path) -> list[date]:
    fechas = sorted(_ediciones(programa.ediciones), reverse=True)
    enviadas = _fechas_enviadas(programa.historial)

    carpeta = destino / programa.clave
    (carpeta / "ediciones").mkdir(parents=True, exist_ok=True)

    vacantes: dict[date, int] = {}
    for fecha in fechas:
        nombre = f"{fecha.isoformat()}.html"
        origen = programa.ediciones / nombre
        shutil.copyfile(origen, carpeta / "ediciones" / nombre)
        vacantes[fecha] = _vacantes_en(origen)

    (carpeta / "index.html").write_text(
        _indice(programa, fechas, enviadas, vacantes), encoding="utf-8"
    )
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


def _tarjeta_edicion(fecha: date, enviada: bool, vacantes: int) -> str:
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


def _indice(
    programa: ProgramaSitio,
    fechas: list[date],
    enviadas: set[date],
    vacantes: dict[date, int],
) -> str:
    if fechas:
        tarjetas = "\n".join(_tarjeta_edicion(f, f in enviadas, vacantes.get(f, 0)) for f in fechas)
        lista = f'    <ul class="ediciones">\n{tarjetas}\n    </ul>'
    else:
        lista = '    <p class="aviso">Todavía no hay ediciones publicadas.</p>'

    cuerpo = f"""  <section class="portada aparece">
    <span class="etiqueta">Boletín quincenal</span>
    <h1>Vacantes para los egresados de {escape(programa.programa)}</h1>
  </section>

  <section class="seccion aparece">
{lista}
  </section>

{_pie_comun()}"""

    return pagina(
        titulo=f"Boletín de empleos — {programa.programa}",
        subtitulo=f"{programa.programa} · Proyección Social",
        descripcion=(
            f"Archivo de ediciones del boletín quincenal de empleos para egresados de "
            f"{programa.programa} de la {INSTITUCION}."
        ),
        cuerpo=cuerpo,
        profundidad="../",
        accion='<a class="boton boton--tenue barra__accion" href="../index.html">Carreras</a>',
    )


def _portada(resumen: list[tuple[ProgramaSitio, list[date]]]) -> str:
    tarjetas = []
    for programa, fechas in resumen:
        if fechas:
            detalle = f"{len(fechas)} ediciones · última, {en_palabras(fechas[0])}"
        else:
            detalle = "Todavía no hay ediciones publicadas"
        tarjetas.append(
            f'      <li><a class="edicion" href="{programa.clave}/index.html">\n'
            f"        <span>\n"
            f'          <span class="edicion__fecha">{escape(programa.programa)}</span><br>\n'
            f'          <span class="edicion__detalle">{escape(detalle)}</span>\n'
            f"        </span>\n"
            f'        <span class="edicion__flecha" aria-hidden="true">›</span>\n'
            f"      </a></li>"
        )

    lista = "\n".join(tarjetas)
    cuerpo = f"""  <section class="portada aparece">
    <span class="etiqueta">Boletín quincenal</span>
    <h1>Vacantes para nuestros egresados</h1>
  </section>

  <section class="seccion aparece">
    <ul class="ediciones">
{lista}
    </ul>
  </section>

{_pie_comun()}"""

    return pagina(
        titulo="Boletín de empleos — Proyección Social",
        descripcion=(
            "Boletín quincenal de empleos para los egresados de la Facultad de Ingenierías "
            f"y Ciencias Básicas de la {INSTITUCION}."
        ),
        cuerpo=cuerpo,
    )


def _pie_comun() -> str:
    return f"""  <footer class="pie aparece">
    <p><strong>{escape(UNIDAD)}</strong><br>{escape(INSTITUCION)} · Armenia, Quindío</p>
    <p>
      Vacantes recogidas del Servicio Público de Empleo, Magneto365, Remotive y Remote OK,
      fuentes que autorizan expresamente su uso. Cada edición cita a las que aportaron ofertas.
    </p>
  </footer>"""


def main(argv: list[str] | None = None) -> int:
    """Entrada para el workflow: `python -m boletin_empleos.sitio`."""
    p = argparse.ArgumentParser(prog="sitio", description="Construye el sitio de ediciones")
    p.add_argument("--programas", type=Path, default=Path("programas"))
    p.add_argument("--datos", type=Path, default=Path("datos"))
    p.add_argument("--destino", type=Path, default=Path("sitio"))
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    programas = programas_desde(args.programas, args.datos)
    if not programas:
        _log.error("no se encontró ninguna carrera en %s", args.programas)
        return 1

    publicadas = construir_sitio(programas, args.destino)
    for clave, fechas in publicadas.items():
        _log.info("%s: %d ediciones", clave, len(fechas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
