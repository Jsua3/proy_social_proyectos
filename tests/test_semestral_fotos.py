"""Las fotos de WhatsApp llegan grandes y a veces giradas: se reducen sin perder la orientación."""

import os

from conftest import foto_jpg
from PIL import Image

from boletin_semestral.fotos import LADO_MAXIMO, PESO_MAXIMO, pequenas, reducir

ORIENTACION = 0x0112


def test_reducir_achica_las_grandes_y_deja_las_pequenas(tmp_path):
    foto_jpg(tmp_path / "grande.jpg", 4000, 3000)
    chica = foto_jpg(tmp_path / "chica.jpg", 1200, 800)
    bytes_antes = chica.read_bytes()

    cambiadas = reducir(tmp_path)

    assert cambiadas == ["grande.jpg"]
    with Image.open(tmp_path / "grande.jpg") as imagen:
        assert max(imagen.size) == LADO_MAXIMO
    assert chica.read_bytes() == bytes_antes


def test_reducir_respeta_la_orientacion(tmp_path):
    ruta = tmp_path / "girada.jpg"
    exif = Image.Exif()
    exif[ORIENTACION] = 6  # la cámara la tomó vertical y la guardó acostada
    Image.new("RGB", (3000, 2000), (200, 30, 30)).save(ruta, exif=exif)

    reducir(tmp_path)

    with Image.open(ruta) as imagen:
        ancho, alto = imagen.size
        assert alto > ancho
        assert imagen.getexif().get(ORIENTACION) in (None, 1)


def test_reducir_baja_el_peso(tmp_path):
    ruta = tmp_path / "ruido.jpg"
    lado = 1800
    Image.frombytes("RGB", (lado, lado), os.urandom(lado * lado * 3)).save(ruta, quality=95)
    assert ruta.stat().st_size > PESO_MAXIMO

    assert reducir(tmp_path) == ["ruido.jpg"]

    assert ruta.stat().st_size <= PESO_MAXIMO


def test_pequenas_avisa_de_las_de_menos_de_mil(tmp_path):
    foto_jpg(tmp_path / "chica.jpg", 800, 600)
    foto_jpg(tmp_path / "buena.jpg", 1200, 800)

    assert pequenas(tmp_path, ["chica.jpg", "buena.jpg"]) == ["chica.jpg"]
