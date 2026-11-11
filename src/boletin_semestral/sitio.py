"""La sección /semestral/ del sitio: copia las ediciones ya publicadas y arma su índice.

No genera nada: cada edición aprobada ya trae su HTML, su PDF y sus fotos en
`datos/semestral/<semestre>/publicada/`. Así lo usan sin navegador ni red los dos
flujos de GitHub que publican el sitio entero (spec §9).
"""

import logging
import shutil
import tomllib
from pathlib import Path

from pydantic import BaseModel, ValidationError

from boletin_semestral.edicion import ARCHIVO
from boletin_semestral.modelo import Estado
from boletin_semestral.render import copiar_estaticos, renderizar_plantilla

_log = logging.getLogger(__name__)


class EdicionPublicada(BaseModel):
    volumen: int
    semestre: str
    fecha: str
    titular: str
    carpeta: Path
    pdf: str


class Anterior(BaseModel):
    volumen: int
    fecha: str
    enlace: str


def publicadas(base: Path) -> list[EdicionPublicada]:
    """Las ediciones aprobadas que ya tienen `publicada/`, de la más reciente a la más vieja."""
    base = Path(base)
    if not base.is_dir():
        return []

    lista = []
    for carpeta in sorted(base.iterdir()):
        publicada = carpeta / "publicada"
        if not (publicada / "index.html").is_file() or not (carpeta / ARCHIVO).is_file():
            continue
        # Una edición ilegible no puede tumbar la publicación del sitio entero.
        try:
            datos = tomllib.loads((carpeta / ARCHIVO).read_text(encoding="utf-8"))
            if datos.get("estado") != Estado.APROBADA:
                continue
            volumen = int(datos["volumen"])
            lista.append(
                EdicionPublicada(
                    volumen=volumen,
                    semestre=str(datos["semestre"]),
                    fecha=str(datos["fecha"]),
                    titular=str(datos.get("portada", {}).get("titular", "")),
                    carpeta=publicada,
                    pdf=f"boletin-vol-{volumen}.pdf",
                )
            )
        except (tomllib.TOMLDecodeError, KeyError, TypeError, ValueError) as e:
            _log.warning("edición semestral ilegible en %s (%s); no se publica", carpeta, e)
    return sorted(lista, key=lambda e: e.volumen, reverse=True)


def anteriores(base: Path) -> list[Anterior]:
    """Los volúmenes previos al programa (`anteriores.toml`), del más reciente al más viejo."""
    archivo = Path(base) / "anteriores.toml"
    if not archivo.is_file():
        return []
    try:
        datos = tomllib.loads(archivo.read_text(encoding="utf-8"))
        lista = [Anterior.model_validate(a) for a in datos.get("anteriores", [])]
    except (tomllib.TOMLDecodeError, ValidationError) as e:
        _log.warning("anteriores.toml ilegible en %s (%s); se omite", archivo, e)
        return []
    return sorted(lista, key=lambda a: a.volumen, reverse=True)


def publicar(base: Path, destino: Path) -> list[EdicionPublicada]:
    """Copia cada edición publicada a `destino/vol-N/` y escribe el índice de la sección."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    lista = publicadas(base)
    for edicion in lista:
        shutil.copytree(edicion.carpeta, destino / f"vol-{edicion.volumen}", dirs_exist_ok=True)
    copiar_estaticos(destino)

    indice = renderizar_plantilla(
        "indice.html.j2",
        ultima=lista[0] if lista else None,
        otras=lista[1:],
        anteriores=anteriores(base),
    )
    (destino / "index.html").write_text(indice, encoding="utf-8")
    _log.info("boletín semestral: %d ediciones publicadas en %s", len(lista), destino)
    return lista
