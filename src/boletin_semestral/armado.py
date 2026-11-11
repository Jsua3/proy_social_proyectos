"""Armar una edición: la vista previa del borrador o la edición publicada.

Un borrador va a `salida/` (que git ignora) con marca y recuadros de pendientes.
Una edición aprobada y sin pendientes va a `datos/semestral/<semestre>/publicada/`,
que se versiona: lo que se aprueba es exactamente lo que se publica (spec §9).
"""

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

    # Se arma desde cero: una foto que ya no está en el archivo no debe quedar publicada.
    if destino.exists():
        shutil.rmtree(destino)
    (destino / "fotos").mkdir(parents=True)
    (destino / "index.html").write_text(renderizar(edicion, modo), encoding="utf-8")
    copiar_estaticos(destino)
    for nombre in nombradas:
        shutil.copy2(carpeta_fotos / nombre, destino / "fotos" / nombre)

    # Se busca al llamar, no como valor por defecto, para que las pruebas puedan reemplazarlo.
    resultado_pdf = (generar or generar_pdf)(destino / "index.html", destino / nombre_pdf)

    return Resultado(
        destino=destino,
        pdf=destino / nombre_pdf,
        pendientes=faltan,
        largas=resultado_pdf.largas,
        reducidas=reducidas,
        pequenas=chicas,
        publicada=publicada,
    )
