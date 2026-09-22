"""El sitio público: el archivo histórico de ediciones de todas las carreras.

El correo solo lleva las vacantes más pertinentes; la edición completa vive aquí.
Además es el rastro con fecha que el CNA pide para el seguimiento a egresados.
"""

import json
from pathlib import Path

from selectolax.parser import HTMLParser

from boletin_empleos.sitio import ProgramaSitio, construir_sitio, main, programas_desde


def _carrera(tmp_path, clave, nombre, ediciones, enviadas=()):
    """Deja en disco las ediciones de una carrera y devuelve su descriptor."""
    carpeta = tmp_path / clave / "ediciones"
    carpeta.mkdir(parents=True, exist_ok=True)
    for fecha, cuerpo in ediciones.items():
        (carpeta / f"{fecha}.html").write_text(cuerpo, encoding="utf-8")

    historial = tmp_path / clave / "historial.json"
    if enviadas:
        historial.write_text(
            json.dumps(
                {"ediciones": [{"numero": i, "fecha": f} for i, f in enumerate(enviadas, 1)]}
            ),
            encoding="utf-8",
        )
    return ProgramaSitio(clave=clave, programa=nombre, ediciones=carpeta, historial=historial)


def _texto(ruta: Path) -> str:
    return HTMLParser(ruta.read_text("utf-8")).text()


def test_cada_carrera_tiene_su_indice_y_sus_ediciones(tmp_path):
    programas = [
        _carrera(tmp_path, "software", "Ingeniería de Software", {"2026-09-21": "<html>a</html>"}),
        _carrera(tmp_path, "industrial", "Ingeniería Industrial", {"2026-09-21": "<html>b</html>"}),
    ]

    construir_sitio(programas, tmp_path / "sitio")

    sitio = tmp_path / "sitio"
    assert (sitio / "software" / "index.html").exists()
    assert (sitio / "industrial" / "index.html").exists()
    assert (sitio / "software" / "ediciones" / "2026-09-21.html").read_text(
        "utf-8"
    ) == "<html>a</html>"
    assert (sitio / "industrial" / "ediciones" / "2026-09-21.html").read_text(
        "utf-8"
    ) == "<html>b</html>"


def test_la_portada_lleva_a_las_dos_carreras(tmp_path):
    programas = [
        _carrera(tmp_path, "software", "Ingeniería de Software", {"2026-09-21": "<html>a</html>"}),
        _carrera(tmp_path, "industrial", "Ingeniería Industrial", {"2026-09-06": "<html>b</html>"}),
    ]

    construir_sitio(programas, tmp_path / "sitio")

    portada = (tmp_path / "sitio" / "index.html").read_text("utf-8")
    enlaces = [a.attributes.get("href") for a in HTMLParser(portada).css("a")]
    assert enlaces == ["software/index.html", "industrial/index.html"]
    assert "Ingeniería de Software" in portada
    assert "Ingeniería Industrial" in portada


def test_el_indice_de_una_carrera_va_de_la_mas_nueva_a_la_mas_vieja(tmp_path):
    programa = _carrera(
        tmp_path,
        "software",
        "Ingeniería de Software",
        {f: "<html></html>" for f in ("2026-09-15", "2026-10-01", "2026-09-01")},
    )

    construir_sitio([programa], tmp_path / "sitio")

    indice = (tmp_path / "sitio" / "software" / "index.html").read_text("utf-8")
    enlaces = [
        a.attributes.get("href")
        for a in HTMLParser(indice).css("a")
        if "ediciones/" in (a.attributes.get("href") or "")
    ]
    assert enlaces == [
        "ediciones/2026-10-01.html",
        "ediciones/2026-09-15.html",
        "ediciones/2026-09-01.html",
    ]


def test_distingue_las_ediciones_enviadas_de_las_vistas_previas(tmp_path):
    """Mientras no haya credenciales de correo, el sitio se llena de vistas previas.

    Decir que se enviaron sería falso: nadie las recibió."""
    programa = _carrera(
        tmp_path,
        "software",
        "Ingeniería de Software",
        {"2026-09-15": "<html></html>", "2026-10-01": "<html></html>"},
        enviadas=("2026-10-01",),
    )

    construir_sitio([programa], tmp_path / "sitio")

    texto = _texto(tmp_path / "sitio" / "software" / "index.html").lower()
    assert "vista previa" in texto
    assert "enviada" in texto


def test_sin_historial_todas_son_vistas_previas(tmp_path):
    programa = _carrera(
        tmp_path, "software", "Ingeniería de Software", {"2026-09-15": "<html></html>"}
    )

    construir_sitio([programa], tmp_path / "sitio")

    texto = _texto(tmp_path / "sitio" / "software" / "index.html").lower()
    assert "vista previa" in texto
    assert "enviada" not in texto, "sin historial, nadie ha recibido nada"


def test_ignora_los_archivos_que_no_son_ediciones(tmp_path):
    """El dry-run deja también la vista previa del correo en la misma carpeta."""
    programa = _carrera(
        tmp_path,
        "software",
        "Ingeniería de Software",
        {"2026-09-15": "<html></html>", "2026-09-15-correo": "<html>correo</html>"},
    )

    publicadas = construir_sitio([programa], tmp_path / "sitio")

    assert [f.isoformat() for f in publicadas["software"]] == ["2026-09-15"]
    assert not (tmp_path / "sitio" / "software" / "ediciones" / "2026-09-15-correo.html").exists()


def test_una_carrera_sin_ediciones_lo_dice_en_vez_de_quedar_vacia(tmp_path):
    programa = _carrera(tmp_path, "industrial", "Ingeniería Industrial", {})

    publicadas = construir_sitio([programa], tmp_path / "sitio")

    assert publicadas["industrial"] == []
    assert "Todavía no hay ediciones" in _texto(tmp_path / "sitio" / "industrial" / "index.html")


def test_el_indice_dice_cuantas_vacantes_trae_cada_edicion(tmp_path):
    """El conteo sale del propio archivo: una edición, un botón por vacante."""
    programa = _carrera(
        tmp_path,
        "software",
        "Ingeniería de Software",
        {"2026-09-15": "<html>" + ">Ver oferta</a>" * 7 + "</html>"},
    )

    construir_sitio([programa], tmp_path / "sitio")

    assert "7 vacantes" in _texto(tmp_path / "sitio" / "software" / "index.html")


def test_los_estaticos_se_comparten_en_la_raiz_del_sitio(tmp_path):
    programa = _carrera(
        tmp_path, "software", "Ingeniería de Software", {"2026-09-15": "<html></html>"}
    )

    construir_sitio([programa], tmp_path / "sitio")

    for estatico in ("estilo.css", "logo-humboldt.png", "movimiento.js"):
        assert (tmp_path / "sitio" / estatico).exists(), f"falta {estatico}"
    indice = (tmp_path / "sitio" / "software" / "index.html").read_text("utf-8")
    assert 'href="../estilo.css"' in indice, "la carrera cuelga un nivel bajo la raíz"


def test_los_programas_se_descubren_desde_sus_archivos_de_configuracion(tmp_path):
    programas = programas_desde(
        Path(__file__).resolve().parents[1] / "programas", tmp_path / "datos"
    )

    claves = {p.clave for p in programas}
    assert {"software", "industrial"} <= claves
    assert all(p.programa for p in programas), "cada uno trae su nombre legible"
    assert any(p.ediciones == tmp_path / "datos" / "software" / "ediciones" for p in programas)


def test_el_comando_construye_el_sitio_y_devuelve_cero(tmp_path):
    """El workflow lo invoca como `python -m boletin_empleos.sitio`."""
    _carrera(tmp_path, "software", "Ingeniería de Software", {"2026-09-15": "<html></html>"})

    codigo = main(
        [
            "--programas",
            str(Path(__file__).resolve().parents[1] / "programas"),
            "--datos",
            str(tmp_path),
            "--destino",
            str(tmp_path / "sitio"),
        ]
    )

    assert codigo == 0
    assert (tmp_path / "sitio" / "index.html").exists()
    assert (tmp_path / "sitio" / "software" / "ediciones" / "2026-09-15.html").exists()
