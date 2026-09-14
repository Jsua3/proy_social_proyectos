from datetime import date

import pytest

from boletin_empleos.almacenamiento import json_repo
from boletin_empleos.almacenamiento.base import HistorialIlegible
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


def test_un_archivo_corrupto_aborta_sin_tocar_el_original(tmp_path):
    # Partir de cero reenviaría todo lo ya enviado y el siguiente registrar
    # sobrescribiría el original (spec §15.4).
    ruta = tmp_path / "historial.json"
    ruta.write_text("{ esto no es json", encoding="utf-8")

    with pytest.raises(HistorialIlegible):
        HistorialJSON(ruta)
    assert ruta.read_text("utf-8") == "{ esto no es json", "el original no se toca"


@pytest.mark.parametrize(
    "contenido",
    [
        b"[]",
        b"null",
        b"42",
        b"{}",
        b'{"ediciones": null}',
        b'{"ediciones": [null]}',
        b'{"ediciones": [{"ids": null}]}',
        b'{"ediciones": [{"ids": "spe:12"}]}',
        b'{"ediciones": [{"ids": [1, 2]}]}',
        b'{"ediciones": [{"ids": ["magneto:dise\xf1o"]}]}',
    ],
    ids=[
        "raiz_lista",
        "raiz_null",
        "raiz_numero",
        "sin_ediciones",
        "ediciones_null",
        "edicion_null",
        "ids_null",
        "ids_cadena_suelta",
        "ids_enteros",
        "bytes_latin1",
    ],
)
def test_forma_o_codificacion_invalida_aborta_sin_tocar_el_original(tmp_path, contenido):
    # Un "ids" como cadena se iteraría letra a letra y uno con enteros nunca
    # coincidiría con los ids reales: las ofertas se reenviarían sin aviso.
    ruta = tmp_path / "historial.json"
    ruta.write_bytes(contenido)

    with pytest.raises(HistorialIlegible):
        HistorialJSON(ruta)
    assert ruta.read_bytes() == contenido


def test_un_bom_utf8_no_se_trata_como_corrupcion(tmp_path):
    # El Bloc de notas de Windows antepone un BOM al guardar en UTF-8.
    ruta = tmp_path / "historial.json"
    valido = '{"ediciones": [{"numero": 1, "fecha": "2026-09-22", "ids": ["spe:1"]}]}'
    ruta.write_bytes(b"\xef\xbb\xbf" + valido.encode("utf-8"))

    h = HistorialJSON(ruta)
    assert h.ids_enviados() == {"spe:1"}
    assert h.numero_edicion() == 2


def test_una_escritura_fallida_conserva_el_historial_anterior(tmp_path, monkeypatch):
    ruta = tmp_path / "historial.json"
    HistorialJSON(ruta).registrar({"spe:1"}, date(2026, 9, 22))
    assert [p.name for p in tmp_path.iterdir()] == ["historial.json"], "no quedan temporales"
    antes = ruta.read_bytes()

    def reemplazo_que_falla(*_args):
        raise OSError("job cancelado a mitad de la escritura")

    monkeypatch.setattr(json_repo.os, "replace", reemplazo_que_falla)
    with pytest.raises(OSError):
        HistorialJSON(ruta).registrar({"spe:2"}, date(2026, 10, 6))
    assert ruta.read_bytes() == antes, "la escritura es atómica: nunca queda un archivo a medias"
