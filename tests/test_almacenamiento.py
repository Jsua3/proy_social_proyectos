from datetime import date

from boletin_empleos.almacenamiento.json_repo import HistorialJSON


def test_historial_vacio_cuando_el_archivo_no_existe(tmp_path):
    h = HistorialJSON(tmp_path / "historial.json")
    assert h.ids_enviados() == set()
    assert h.numero_edicion() == 1


def test_registrar_persiste_los_ids(tmp_path):
    ruta = tmp_path / "historial.json"
    HistorialJSON(ruta).registrar({"spe:1", "spe:2"}, date(2026, 9, 22))

    recargado = HistorialJSON(ruta)
    assert recargado.ids_enviados() == {"spe:1", "spe:2"}
    assert recargado.numero_edicion() == 2


def test_registrar_acumula_entre_ediciones(tmp_path):
    ruta = tmp_path / "historial.json"
    h = HistorialJSON(ruta)
    h.registrar({"spe:1"}, date(2026, 9, 22))
    HistorialJSON(ruta).registrar({"spe:2"}, date(2026, 10, 6))

    final = HistorialJSON(ruta)
    assert final.ids_enviados() == {"spe:1", "spe:2"}
    assert final.numero_edicion() == 3


def test_el_archivo_es_json_legible_y_ordenado(tmp_path):
    import json

    ruta = tmp_path / "historial.json"
    HistorialJSON(ruta).registrar({"spe:2", "spe:1"}, date(2026, 9, 22))
    datos = json.loads(ruta.read_text("utf-8"))

    assert datos["ediciones"][0]["fecha"] == "2026-09-22"
    assert datos["ediciones"][0]["ids"] == ["spe:1", "spe:2"], "ordenado para diffs limpios en git"


def test_tolera_un_archivo_corrupto(tmp_path):
    ruta = tmp_path / "historial.json"
    ruta.write_text("{ esto no es json", encoding="utf-8")
    assert HistorialJSON(ruta).ids_enviados() == set()
