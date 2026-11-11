"""La sección /semestral/ del sitio: solo ediciones aprobadas, la última destacada y el archivo."""

from conftest import edicion_publicada

from boletin_semestral.sitio import anteriores, publicadas, publicar

ANTERIORES_CON_VOL_7 = """\
[[anteriores]]
volumen = 7
fecha = "Junio 2026"
enlace = "https://heyzine.com/flip-book/df92099d87.html"
"""


def test_solo_se_publican_las_aprobadas_con_publicada(tmp_path):
    edicion_publicada(tmp_path, "2026-2", 8)
    edicion_publicada(tmp_path, "2027-1", 9, aprobada=False, con_publicada=False)

    assert [e.volumen for e in publicadas(tmp_path)] == [8]


def test_la_mas_reciente_va_primero(tmp_path):
    edicion_publicada(tmp_path, "2026-2", 8)
    edicion_publicada(tmp_path, "2027-1", 9)

    assert [e.volumen for e in publicadas(tmp_path)] == [9, 8]


def test_publicar_copia_y_arma_el_indice(tmp_path):
    base = tmp_path / "semestral"
    edicion_publicada(base, "2026-2", 8)
    destino = tmp_path / "sitio" / "semestral"

    publicar(base, destino)

    assert (destino / "vol-8" / "index.html").is_file()
    assert (destino / "vol-8" / "boletin-vol-8.pdf").is_file()
    assert (destino / "estilo.css").is_file()
    indice = (destino / "index.html").read_text(encoding="utf-8")
    assert 'href="vol-8/index.html"' in indice
    assert 'href="vol-8/boletin-vol-8.pdf"' in indice
    assert "Titular del Vol. 8" in indice


def test_indice_lista_las_anteriores(tmp_path):
    base = tmp_path / "semestral"
    edicion_publicada(base, "2026-2", 8)
    (base / "anteriores.toml").write_text(ANTERIORES_CON_VOL_7, encoding="utf-8")
    destino = tmp_path / "sitio" / "semestral"

    publicar(base, destino)

    indice = (destino / "index.html").read_text(encoding="utf-8")
    assert "https://heyzine.com/flip-book/df92099d87.html" in indice
    assert 'rel="noopener"' in indice
    assert "Vol. 7" in indice


def test_indice_sin_nada(tmp_path):
    base = tmp_path / "semestral"
    base.mkdir()
    destino = tmp_path / "sitio" / "semestral"

    assert publicar(base, destino) == []

    assert "Todavía no hay ediciones publicadas." in (destino / "index.html").read_text("utf-8")


def test_anteriores_ausente_es_lista_vacia(tmp_path):
    assert anteriores(tmp_path) == []
