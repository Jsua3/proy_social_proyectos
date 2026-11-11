"""Armar una edición: la vista previa del borrador o la edición publicada.

Un borrador va a `salida/` (que git ignora) con marca y recuadros de pendientes.
Una edición aprobada y sin pendientes va a `datos/semestral/<semestre>/publicada/`,
que se versiona: lo que se aprueba es exactamente lo que se publica (spec §9).
"""

import contextlib
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from boletin_semestral.edicion import ErrorEdicion, cargar
from boletin_semestral.fotos import pequenas, reducir
from boletin_semestral.modelo import Estado, Pendiente, fotos_nombradas, pendientes
from boletin_semestral.pdf import ResultadoPdf, generar_pdf
from boletin_semestral.render import Modo, copiar_estaticos, renderizar

GeneradorPdf = Callable[[Path, Path], ResultadoPdf]


class Resultado(NamedTuple):
    destino: Path
    pdf: Path
    pendientes: list[Pendiente]
    largas: list[tuple[str, int]]
    reducidas: list[str]
    pequenas: list[str]
    publicada: bool


def armar(carpeta: Path, salida: Path, generar: GeneradorPdf | None = None) -> Resultado:
    """Genera la web y el PDF de la edición; ver el docstring del módulo."""
    carpeta = Path(carpeta)
    edicion = cargar(carpeta)
    carpeta_fotos = carpeta / "fotos"
    reducidas = reducir(carpeta_fotos) if carpeta_fotos.is_dir() else []
    nombradas = fotos_nombradas(edicion)
    chicas = pequenas(carpeta_fotos, nombradas)
    faltan = pendientes(edicion)

    publicada = edicion.estado is Estado.APROBADA
    if publicada:
        if faltan:
            lista = "\n".join(f"- {p.lugar}: {p.motivo}" for p in faltan)
            raise ErrorEdicion(f"La edición está aprobada pero tiene pendientes:\n{lista}")
        destino = carpeta / "publicada"
        modo = Modo.FINAL
        nombre_pdf = f"boletin-vol-{edicion.volumen}.pdf"
    else:
        destino = Path(salida) / edicion.semestre
        modo = Modo.BORRADOR
        nombre_pdf = f"boletin-vol-{edicion.volumen}-borrador.pdf"

    # Se arma desde cero en una carpeta aparte y solo se pone en su sitio si todo salió
    # bien: si falla el PDF, no queda una `publicada/` a medias que el sitio publique.
    temporal = destino.with_name(destino.name + ".armando")
    _borrar_sin_fallar(temporal)
    (temporal / "fotos").mkdir(parents=True)
    try:
        (temporal / "index.html").write_text(renderizar(edicion, modo), encoding="utf-8")
        copiar_estaticos(temporal)
        for nombre in nombradas:
            shutil.copy2(carpeta_fotos / nombre, temporal / "fotos" / nombre)
        # Se busca al llamar, no como valor por defecto, para que las pruebas puedan reemplazarlo.
        resultado_pdf = (generar or generar_pdf)(temporal / "index.html", temporal / nombre_pdf)
    except BaseException:
        _borrar_sin_fallar(temporal)
        raise
    _reemplazar(temporal, destino)

    return Resultado(
        destino=destino,
        pdf=destino / nombre_pdf,
        pendientes=faltan,
        largas=resultado_pdf.largas,
        reducidas=reducidas,
        pequenas=chicas,
        publicada=publicada,
    )


def _reemplazar(temporal: Path, destino: Path) -> None:
    """Pone la carpeta nueva en lugar de la vieja; una foto quitada no queda publicada."""
    anterior = destino.with_name(destino.name + ".anterior")
    if destino.exists():
        _borrar_sin_fallar(anterior)
        try:
            destino.rename(anterior)
        except PermissionError:
            _borrar_sin_fallar(temporal)
            raise ErrorEdicion(
                f"No se pudo reemplazar {destino}: hay un archivo abierto, casi siempre el PDF "
                "en un visor. Ciérralo y vuelve a correr armar."
            ) from None
    temporal.rename(destino)
    _borrar_sin_fallar(anterior)


def _borrar_sin_fallar(carpeta: Path) -> None:
    with contextlib.suppress(OSError):
        shutil.rmtree(carpeta, ignore_errors=True)
