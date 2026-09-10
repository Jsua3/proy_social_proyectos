# tests/test_fuente_remoteok.py
import json
from pathlib import Path

import httpx
import respx

from boletin_empleos.fuentes.remoteok import FuenteRemoteOK
from boletin_empleos.modelos import Modalidad

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "remoteok.json").read_text("utf-8"))


@respx.mock
def test_remoteok_descarta_el_aviso_legal():
    respx.get("https://remoteok.com/api").mock(return_value=httpx.Response(200, json=FIXTURE))
    ofertas = FuenteRemoteOK().obtener()

    assert len(ofertas) == len(FIXTURE) - 1, "el primer elemento es el aviso legal, no una oferta"
    assert all(o.modalidad is Modalidad.REMOTO for o in ofertas)
    assert all(o.fuente == "remoteok" for o in ofertas)


def test_remoteok_declara_su_permiso_y_atribucion():
    f = FuenteRemoteOK()
    assert f.nombre == "remoteok"
    assert "Remote OK" in f.atribucion
    assert f.base_permiso


@respx.mock
def test_remoteok_devuelve_vacio_si_la_api_falla():
    respx.get("https://remoteok.com/api").mock(return_value=httpx.Response(500))
    assert FuenteRemoteOK().obtener() == []
