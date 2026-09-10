# tests/test_fuente_remotive.py
import json
from pathlib import Path

import httpx
import respx

from boletin_empleos.fuentes.remotive import FuenteRemotive
from boletin_empleos.modelos import Modalidad

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "remotive.json").read_text("utf-8"))


@respx.mock
def test_remotive_normaliza_ofertas():
    respx.get(url__startswith="https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json=FIXTURE)
    )
    ofertas = FuenteRemotive().obtener()

    assert len(ofertas) == len(FIXTURE["jobs"])
    o = ofertas[0]
    assert o.fuente == "remotive"
    assert o.id.startswith("remotive:")
    assert o.modalidad is Modalidad.REMOTO
    assert o.titulo
    assert str(o.url).startswith("http")


def test_remotive_declara_su_permiso_y_atribucion():
    f = FuenteRemotive()
    assert f.nombre == "remotive"
    assert f.base_permiso
    assert "Remotive" in f.atribucion
    assert str(f.url_atribucion).startswith("https://remotive.com")
    assert 0.0 <= f.confianza_base <= 1.0


@respx.mock
def test_remotive_devuelve_vacio_si_la_api_falla():
    respx.get(url__startswith="https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(503)
    )
    assert FuenteRemotive().obtener() == []
