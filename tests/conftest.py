"""Datos de prueba compartidos por las pruebas del boletín semestral."""

import tomllib
from pathlib import Path

import pytest
from PIL import Image

EDICION_COMPLETA = """\
volumen = 8
semestre = "2026-2"
fecha = "Diciembre 2026"
estado = "borrador"

[portada]
titular = "Ecohumboldt, entre las 20 experiencias del país en acción climática"
foto = "portada.jpg"

[editorial]
titulo = "Construyendo *impacto* desde la academia"
cuerpo = "Primer párrafo.\\n\\nSegundo párrafo con **negrita**."
firma = "Coordinación de Proyección Social"

[[secciones]]
tipo = "cifras"
etiqueta = "Cifras"
titulo = "El semestre en *números*"
foto = "siembra.jpg"
cifras = [
  { valor = "20", texto = "experiencias significativas" },
  { valor = "4", texto = "emprendimientos" },
]

[[secciones]]
tipo = "texto"
etiqueta = "Planeta"
titulo = "Nuestro compromiso con el *planeta*"
cuerpo = "VII jornada de siembra."
fotos = [{ archivo = "siembra.jpg", pie = "Siembra" }, { archivo = "taller.jpg", pie = "Taller" }]

[[secciones]]
tipo = "proyectos"
etiqueta = "Comunidades"
titulo = "Proyectos que *transforman*"

[[secciones.proyectos]]
nombre = "Huellas con Bienestar"
docentes = ["Diana María Melo Taborda"]
programas = ["Ingeniería de Software", "Medicina Veterinaria"]
descripcion = "Bienestar animal."
foto = "taller.jpg"

[[secciones]]
tipo = "comparativo"
etiqueta = "Prácticas empresariales"
titulo = "Indicadores de *prácticas*"
periodo_anterior = "2025-2"
periodo_actual = "2026-2"
meta = 80

[[secciones.grupos]]
nombre = "Ingeniería Industrial"
indicadores = [{ nombre = "Impacto de la empresa", anterior = 90.0, actual = 100.0 }]

[[secciones]]
tipo = "videos"
etiqueta = "Videos"
titulo = "Videos de la *proyección social*"

[[secciones.videos]]
titulo = "Siembra 2026"
enlace = "https://www.youtube.com/watch?v=abc123XYZ00"
miniatura = "siembra.jpg"

[[secciones]]
tipo = "imagen"
etiqueta = "Sistema"
titulo = "Sistema de *proyección social*"
archivo = "sistema.png"
descripcion = "Ejes, líneas y productos del sistema de proyección social"
"""

FOTOS_DE_LA_EDICION = ("portada.jpg", "siembra.jpg", "taller.jpg", "sistema.png")


def foto_jpg(ruta: Path, ancho: int = 1200, alto: int = 800) -> Path:
    """Una imagen lisa del tamaño pedido; el formato sale de la extensión."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (ancho, alto), (20, 61, 104)).save(ruta)
    return ruta


@pytest.fixture
def carpeta_edicion(tmp_path) -> Path:
    """Una edición 2026-2 completa, sin pendientes, con todas sus fotos."""
    carpeta = tmp_path / "semestral" / "2026-2"
    carpeta.mkdir(parents=True)
    (carpeta / "edicion.toml").write_text(EDICION_COMPLETA, encoding="utf-8")
    for nombre in FOTOS_DE_LA_EDICION:
        foto_jpg(carpeta / "fotos" / nombre)
    return carpeta


def edicion_publicada(
    base: Path, semestre: str, volumen: int, *, aprobada: bool = True, con_publicada: bool = True
) -> Path:
    """Deja en disco una edición como la dejaría `semestral armar`: TOML y, si toca, publicada/."""
    carpeta = base / semestre
    carpeta.mkdir(parents=True)
    anio, mitad = semestre.split("-")
    fecha = f"{'Junio' if mitad == '1' else 'Diciembre'} {anio}"
    (carpeta / "edicion.toml").write_text(
        f'volumen = {volumen}\nsemestre = "{semestre}"\nfecha = "{fecha}"\n'
        f'estado = "{"aprobada" if aprobada else "borrador"}"\nsecciones = []\n\n'
        f'[portada]\ntitular = "Titular del Vol. {volumen}"\n\n[editorial]\ncuerpo = "Texto."\n',
        encoding="utf-8",
    )
    if con_publicada:
        publicada = carpeta / "publicada"
        publicada.mkdir()
        (publicada / "index.html").write_text(f"<html>Vol. {volumen}</html>", encoding="utf-8")
        (publicada / f"boletin-vol-{volumen}.pdf").write_bytes(b"%PDF-falso")
    return carpeta


def leer_datos(carpeta: Path) -> dict:
    """El TOML de una edición como diccionario, para modificarlo en las pruebas."""
    with (carpeta / "edicion.toml").open("rb") as f:
        return tomllib.load(f)
