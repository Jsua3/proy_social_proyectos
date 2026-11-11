"""Cargar una edición con mensajes que un monitor entienda, y crear la del semestre siguiente."""

import pytest
from conftest import EDICION_COMPLETA

from boletin_semestral.edicion import ErrorEdicion, cargar, nueva
from boletin_semestral.modelo import pendientes

ANTERIORES_CON_VOL_7 = """\
[[anteriores]]
volumen = 7
fecha = "Junio 2026"
enlace = "https://heyzine.com/flip-book/df92099d87.html"
"""

ETIQUETAS_DEL_VOL_7 = [
    "Cifras",
    "Comunidades",
    "Planeta",
    "Monitores",
    "Sistema",
    "Prácticas empresariales",
    "Aprendizaje con impacto",
    "Egresados",
    "Docentes",
    "Videos",
]


def _reescribir(carpeta, viejo: str, nuevo: str) -> None:
    archivo = carpeta / "edicion.toml"
    texto = archivo.read_text(encoding="utf-8")
    assert viejo in texto
    archivo.write_text(texto.replace(viejo, nuevo, 1), encoding="utf-8")


def test_cargar_una_edicion_valida(carpeta_edicion):
    assert cargar(carpeta_edicion).volumen == 8


def test_toml_roto_dice_la_linea(carpeta_edicion):
    _reescribir(carpeta_edicion, 'fecha = "Diciembre 2026"', 'fecha = "sin cerrar')

    with pytest.raises(ErrorEdicion, match="línea 3"):
        cargar(carpeta_edicion)


def test_error_de_validacion_nombra_seccion_campo_y_valor(carpeta_edicion):
    _reescribir(carpeta_edicion, "actual = 100.0", "actual = 101.0")

    with pytest.raises(ErrorEdicion) as error:
        cargar(carpeta_edicion)

    mensaje = str(error.value)
    assert "Sección 4" in mensaje
    assert "Indicadores de *prácticas*" in mensaje
    assert "indicadores[0].actual" in mensaje


def test_tipo_desconocido_lista_los_validos(carpeta_edicion):
    _reescribir(carpeta_edicion, 'tipo = "cifras"', 'tipo = "foto"')

    with pytest.raises(ErrorEdicion) as error:
        cargar(carpeta_edicion)

    assert "texto, cifras, proyectos, comparativo, videos, imagen" in str(error.value)


def test_foto_que_no_existe(carpeta_edicion):
    (carpeta_edicion / "fotos" / "taller.jpg").unlink()

    with pytest.raises(ErrorEdicion, match="taller.jpg"):
        cargar(carpeta_edicion)


def test_foto_con_otras_mayusculas_no_cuenta(carpeta_edicion):
    fotos = carpeta_edicion / "fotos"
    (fotos / "siembra.jpg").rename(fotos / "Siembra.JPG")

    with pytest.raises(ErrorEdicion, match="siembra.jpg"):
        cargar(carpeta_edicion)


def test_carpeta_y_semestre_deben_coincidir(carpeta_edicion):
    otra = carpeta_edicion.rename(carpeta_edicion.parent / "2027-1")

    with pytest.raises(ErrorEdicion, match="2027-1"):
        cargar(otra)


def test_nueva_sin_anteriores_usa_el_esqueleto(tmp_path):
    base = tmp_path / "semestral"
    base.mkdir()
    (base / "anteriores.toml").write_text(ANTERIORES_CON_VOL_7, encoding="utf-8")

    carpeta = nueva(base, "2026-2")
    edicion = cargar(carpeta)

    assert carpeta == base / "2026-2"
    assert edicion.volumen == 8
    assert edicion.fecha == "Diciembre 2026"
    assert [s.etiqueta for s in edicion.secciones] == ETIQUETAS_DEL_VOL_7
    assert len(pendientes(edicion)) == 12
    assert (carpeta / "edicion.toml").read_text(encoding="utf-8").startswith("#")
    assert (carpeta / "fotos").is_dir()


def test_nueva_copia_la_estructura_de_la_anterior(carpeta_edicion):
    anterior = cargar(carpeta_edicion)

    edicion = cargar(nueva(carpeta_edicion.parent, "2027-1"))

    assert edicion.volumen == 9
    assert edicion.fecha == "Junio 2027"
    assert edicion.estado == "borrador"
    assert [(s.tipo, s.etiqueta, s.titulo) for s in edicion.secciones] == [
        (s.tipo, s.etiqueta, s.titulo) for s in anterior.secciones
    ]
    assert edicion.secciones[0].cifras == []
    assert all(s.pendiente for s in edicion.secciones)
    assert edicion.portada.titular == ""


def test_nueva_no_sobrescribe(carpeta_edicion):
    with pytest.raises(ErrorEdicion, match="ya existe"):
        nueva(carpeta_edicion.parent, "2026-2")

    assert (carpeta_edicion / "edicion.toml").read_text(encoding="utf-8") == EDICION_COMPLETA


def test_nueva_rechaza_semestre_mal_escrito(tmp_path):
    with pytest.raises(ErrorEdicion, match="2026-02"):
        nueva(tmp_path, "2026-02")
