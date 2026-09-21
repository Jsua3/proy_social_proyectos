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

_log = logging.getLogger(__name__)

# Solo `AAAA-MM-DD.html` es una edición. En la misma carpeta pueden quedar otros
# archivos: el dry-run deja además la vista previa del correo.
_NOMBRE_EDICION = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")

_MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def construir_sitio(ediciones: Path, destino: Path, historial: Path | None = None) -> list[date]:
    """Copia las ediciones al sitio y escribe el índice. Devuelve las publicadas."""
    fechas = sorted(_ediciones(Path(ediciones)), reverse=True)
    enviadas = _fechas_enviadas(historial)

    destino = Path(destino)
    (destino / "ediciones").mkdir(parents=True, exist_ok=True)
    for fecha in fechas:
        nombre = f"{fecha.isoformat()}.html"
        shutil.copyfile(Path(ediciones) / nombre, destino / "ediciones" / nombre)

    (destino / "index.html").write_text(_indice(fechas, enviadas), encoding="utf-8")
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


def _en_palabras(fecha: date) -> str:
    return f"{fecha.day} de {_MESES[fecha.month - 1]} de {fecha.year}"


def _fila(fecha: date, enviada: bool) -> str:
    estado = "enviada a la Coordinación" if enviada else "vista previa"
    clase = "enviada" if enviada else "previa"
    return (
        f'    <li><a href="ediciones/{fecha.isoformat()}.html">'
        f"{escape(_en_palabras(fecha))}</a>"
        f' <span class="estado {clase}">{estado}</span></li>'
    )


def _indice(fechas: list[date], enviadas: set[date]) -> str:
    if fechas:
        cuerpo = (
            "  <ul class='ediciones'>\n"
            + "\n".join(_fila(f, f in enviadas) for f in fechas)
            + "\n  </ul>"
        )
    else:
        cuerpo = "  <p class='vacio'>Todavía no hay ediciones publicadas.</p>"

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Boletín de empleos — Ingeniería de Software</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    line-height: 1.6;
    max-width: 44rem;
    margin: 0 auto;
    padding: 2rem 1rem 4rem;
  }}
  h1 {{ font-size: 1.6rem; margin-bottom: 0.2rem; }}
  .institucion {{ color: #5a6570; margin-top: 0; }}
  .ediciones {{ list-style: none; padding: 0; }}
  .ediciones li {{
    padding: 0.7rem 0;
    border-bottom: 1px solid rgba(128, 128, 128, 0.3);
  }}
  .estado {{ font-size: 0.85rem; color: #5a6570; }}
  .estado.previa::before {{ content: "· "; }}
  .estado.enviada::before {{ content: "· "; }}
  footer {{ margin-top: 2.5rem; font-size: 0.85rem; color: #5a6570; }}
</style>
</head>
<body>
  <h1>Boletín de empleos — Ingeniería de Software</h1>
  <p class="institucion">
    Proyección Social · Facultad de Ingenierías y Ciencias Básicas<br>
    Corporación Universitaria Empresarial Alexander von Humboldt · Armenia, Quindío
  </p>
  <p>
    Cada quince días, un agente recoge vacantes de desarrollo de software, las filtra
    por pertinencia para los egresados del programa y comprueba que el enlace siga
    vivo. Aquí queda cada edición completa.
  </p>
{cuerpo}
  <footer>
    Vacantes recogidas del Servicio Público de Empleo, Magneto365, Remotive y Remote OK,
    fuentes que autorizan expresamente su uso. Cada edición cita a las que aportaron
    ofertas.
  </footer>
</body>
</html>
"""


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
