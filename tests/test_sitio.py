"""El sitio público: el archivo histórico de ediciones que enlaza cada correo.

El correo solo lleva las vacantes más pertinentes; la edición completa vive aquí.
Además es el rastro con fecha que el CNA pide para el seguimiento a egresados.
"""

import json

from selectolax.parser import HTMLParser

from boletin_empleos.sitio import construir_sitio, main


def _edicion(directorio, fecha: str, cuerpo: str = "<html>edición</html>"):
    directorio.mkdir(parents=True, exist_ok=True)
    (directorio / f"{fecha}.html").write_text(cuerpo, encoding="utf-8")


def test_copia_cada_edicion_al_sitio(tmp_path):
    ediciones = tmp_path / "ediciones"
    _edicion(ediciones, "2026-09-15", "<html>quince</html>")
    _edicion(ediciones, "2026-10-01", "<html>primero</html>")

    construir_sitio(ediciones, tmp_path / "sitio")

    destino = tmp_path / "sitio" / "ediciones"
    assert (destino / "2026-09-15.html").read_text("utf-8") == "<html>quince</html>"
    assert (destino / "2026-10-01.html").read_text("utf-8") == "<html>primero</html>"


def test_el_indice_lista_las_ediciones_de_la_mas_nueva_a_la_mas_vieja(tmp_path):
    ediciones = tmp_path / "ediciones"
    for fecha in ("2026-09-15", "2026-10-01", "2026-09-01"):
        _edicion(ediciones, fecha)

    construir_sitio(ediciones, tmp_path / "sitio")

    arbol = HTMLParser((tmp_path / "sitio" / "index.html").read_text("utf-8"))
    enlaces = [a.attributes.get("href") for a in arbol.css("a")]
    assert enlaces == [
        "ediciones/2026-10-01.html",
        "ediciones/2026-09-15.html",
        "ediciones/2026-09-01.html",
    ]


def test_distingue_las_ediciones_enviadas_de_las_vistas_previas(tmp_path):
    """Mientras no haya credenciales de correo, el sitio se llena de vistas previas.

    Decir que se enviaron sería falso: nadie las recibió."""
    ediciones = tmp_path / "ediciones"
    _edicion(ediciones, "2026-09-15")
    _edicion(ediciones, "2026-10-01")
    historial = tmp_path / "historial.json"
    historial.write_text(
        json.dumps({"ediciones": [{"numero": 1, "fecha": "2026-10-01", "ids": ["x:1"]}]}),
        encoding="utf-8",
    )

    construir_sitio(ediciones, tmp_path / "sitio", historial)

    texto = HTMLParser((tmp_path / "sitio" / "index.html").read_text("utf-8")).text()
    assert "vista previa" in texto
    assert "enviada" in texto


def test_sin_historial_todas_son_vistas_previas(tmp_path):
    ediciones = tmp_path / "ediciones"
    _edicion(ediciones, "2026-09-15")

    construir_sitio(ediciones, tmp_path / "sitio", tmp_path / "no-existe.json")

    texto = HTMLParser((tmp_path / "sitio" / "index.html").read_text("utf-8")).text()
    assert "vista previa" in texto
    assert "enviada" not in texto


def test_ignora_los_archivos_que_no_son_ediciones(tmp_path):
    """El dry-run deja también la vista previa del correo en la misma carpeta."""
    ediciones = tmp_path / "ediciones"
    _edicion(ediciones, "2026-09-15")
    (ediciones / "2026-09-15-correo.html").write_text("<html>correo</html>", encoding="utf-8")
    (ediciones / "notas.txt").write_text("nada", encoding="utf-8")

    publicadas = construir_sitio(ediciones, tmp_path / "sitio")

    assert [f.isoformat() for f in publicadas] == ["2026-09-15"]
    assert not (tmp_path / "sitio" / "ediciones" / "2026-09-15-correo.html").exists()


def test_sin_ediciones_el_indice_lo_dice_en_vez_de_quedar_vacio(tmp_path):
    publicadas = construir_sitio(tmp_path / "ediciones", tmp_path / "sitio")

    assert publicadas == []
    texto = HTMLParser((tmp_path / "sitio" / "index.html").read_text("utf-8")).text()
    assert "Todavía no hay ediciones" in texto


def test_el_indice_nombra_la_institucion_y_las_fuentes(tmp_path):
    """La atribución a los portales viaja en cada edición; el índice dice de dónde salen."""
    _edicion(tmp_path / "ediciones", "2026-09-15")

    construir_sitio(tmp_path / "ediciones", tmp_path / "sitio")

    texto = HTMLParser((tmp_path / "sitio" / "index.html").read_text("utf-8")).text()
    assert "Alexander von Humboldt" in texto
    assert "Servicio Público de Empleo" in texto


def test_el_comando_construye_el_sitio_y_devuelve_cero(tmp_path):
    """El workflow lo invoca como `python -m boletin_empleos.sitio`."""
    _edicion(tmp_path / "ediciones", "2026-09-15")

    codigo = main(
        [
            "--ediciones",
            str(tmp_path / "ediciones"),
            "--destino",
            str(tmp_path / "sitio"),
            "--historial",
            str(tmp_path / "historial.json"),
        ]
    )

    assert codigo == 0
    assert (tmp_path / "sitio" / "index.html").exists()
    assert (tmp_path / "sitio" / "ediciones" / "2026-09-15.html").exists()
