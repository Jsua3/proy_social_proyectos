"""Las fotos llegan de WhatsApp: pesadas y, a veces, giradas. Se reducen en el lugar.

El repositorio es público y cada semestre suma fotos; guardarlas reducidas evita
que crezca sin necesidad (spec §13).
"""

import io
from pathlib import Path

from PIL import Image, ImageOps

from boletin_semestral.edicion import ErrorEdicion

LADO_MAXIMO = 1800
PESO_MAXIMO = 1_500_000
ANCHO_MINIMO = 1000

_EXTENSIONES = {".jpg", ".jpeg", ".png"}
_CALIDAD_INICIAL = 85
_CALIDAD_MINIMA = 60


def reducir(carpeta_fotos: Path) -> list[str]:
    """Reduce las fotos que pasan del lado o del peso máximo. Devuelve las que cambió."""
    cambiadas = []
    for ruta in sorted(Path(carpeta_fotos).iterdir()):
        if ruta.suffix.lower() not in _EXTENSIONES:
            continue
        try:
            with Image.open(ruta) as imagen:
                demasiado_grande = max(imagen.size) > LADO_MAXIMO
            if demasiado_grande or ruta.stat().st_size > PESO_MAXIMO:
                _reducir_una(ruta)
                cambiadas.append(ruta.name)
        except OSError:
            raise _ilegible(ruta.name) from None
    return cambiadas


def pequenas(carpeta_fotos: Path, nombres: list[str]) -> list[str]:
    """Las fotos de menos de ANCHO_MINIMO px de ancho: en el PDF se verán borrosas."""
    resultado = []
    for nombre in nombres:
        try:
            with Image.open(Path(carpeta_fotos) / nombre) as imagen:
                if imagen.size[0] < ANCHO_MINIMO:
                    resultado.append(nombre)
        except OSError:
            raise _ilegible(nombre) from None
    return resultado


def _ilegible(nombre: str) -> ErrorEdicion:
    return ErrorEdicion(
        f"No se pudo leer la foto {nombre}: no es una imagen JPG o PNG válida. "
        "Las fotos HEIC del iPhone hay que convertirlas a JPG."
    )


def _reducir_una(ruta: Path) -> None:
    with Image.open(ruta) as original:
        # Primero se endereza: al reescribirla se pierde la etiqueta EXIF que
        # le decía al visor cómo girarla.
        imagen = ImageOps.exif_transpose(original)
        imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO))

    if ruta.suffix.lower() == ".png":
        imagen.save(ruta, optimize=True)
        return

    imagen = imagen.convert("RGB")
    datos = _jpg(imagen, _CALIDAD_INICIAL)
    calidad = _CALIDAD_INICIAL
    while len(datos) > PESO_MAXIMO and calidad > _CALIDAD_MINIMA:
        calidad -= 10
        datos = _jpg(imagen, calidad)
    # Si ni con la calidad mínima cabe, se achica la imagen hasta que quepa.
    while len(datos) > PESO_MAXIMO:
        imagen = imagen.resize((int(imagen.width * 0.85), int(imagen.height * 0.85)))
        datos = _jpg(imagen, calidad)
    ruta.write_bytes(datos)


def _jpg(imagen: Image.Image, calidad: int) -> bytes:
    salida = io.BytesIO()
    imagen.save(salida, format="JPEG", quality=calidad, optimize=True)
    return salida.getvalue()
