"""El borrador con Claude es opcional: propone textos aparte y nunca toca la edición."""

import hashlib
import json
import tomllib

from boletin_semestral.borrador import Redactor, Sugerencias, escribir_sugerencias
from boletin_semestral.cli import main
from boletin_semestral.edicion import cargar

RESPUESTA = json.dumps(
    {
        "sugerencias": [
            {
                "seccion": "Planeta",
                "cuerpo": "Se realizó la VII jornada institucional de siembra de árboles.",
                "cifras": [],
                "proyectos": [],
            },
            {
                "seccion": "Cifras",
                "cuerpo": "",
                "cifras": [{"valor": "4", "texto": "emprendimientos acompañados"}],
                "proyectos": [],
            },
        ]
    }
)


def _responder(texto):
    return lambda self, prompt: texto


def test_proponer_devuelve_sugerencias_validas(monkeypatch, carpeta_edicion):
    monkeypatch.setattr(Redactor, "_pedir", _responder(RESPUESTA))

    sugerencias = Redactor().proponer("Texto del correo", cargar(carpeta_edicion))

    assert len(sugerencias.sugerencias) == 2
    assert sugerencias.sugerencias[1].cifras[0].valor == "4"


def test_respuesta_invalida_devuelve_none(monkeypatch, carpeta_edicion):
    monkeypatch.setattr(Redactor, "_pedir", _responder("no es json"))

    assert Redactor().proponer("Texto del correo", cargar(carpeta_edicion)) is None


def test_fallo_del_proveedor_devuelve_none(monkeypatch, carpeta_edicion):
    def caido(self, prompt):
        raise RuntimeError("el proveedor no responde")

    monkeypatch.setattr(Redactor, "_pedir", caido)

    assert Redactor().proponer("Texto del correo", cargar(carpeta_edicion)) is None


def test_el_prompt_prohibe_inventar_y_lista_las_secciones(monkeypatch, carpeta_edicion):
    pedidos = []

    def capturar(self, prompt):
        pedidos.append(prompt)
        return RESPUESTA

    monkeypatch.setattr(Redactor, "_pedir", capturar)

    Redactor().proponer("Sembramos 300 árboles en Filandia.", cargar(carpeta_edicion))

    prompt = pedidos[0]
    assert "no inventes cifras" in prompt
    assert "Planeta" in prompt
    assert "Nuestro compromiso con el planeta" in prompt
    assert "Sembramos 300 árboles en Filandia." in prompt


def test_escribir_sugerencias_es_toml_valido(tmp_path):
    destino = tmp_path / "borrador-sugerido.toml"

    escribir_sugerencias(Sugerencias.model_validate_json(RESPUESTA), destino)

    with destino.open("rb") as f:
        datos = tomllib.load(f)
    assert datos["sugerencias"][0]["seccion"] == "Planeta"


def _huella(ruta) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def test_cli_borrador_escribe_aparte_y_no_toca_la_edicion(monkeypatch, carpeta_edicion, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-de-prueba")
    monkeypatch.setattr(Redactor, "_pedir", _responder(RESPUESTA))
    correo = tmp_path / "correo.txt"
    correo.write_text("Actividades del semestre.", encoding="utf-8")
    antes = _huella(carpeta_edicion / "edicion.toml")

    codigo = main(
        ["borrador", "2026-2", "--correo", str(correo), "--datos", str(carpeta_edicion.parent)]
    )

    assert codigo == 0
    assert (carpeta_edicion / "borrador-sugerido.toml").is_file()
    assert _huella(carpeta_edicion / "edicion.toml") == antes


def test_cli_borrador_sin_clave(monkeypatch, capsys, carpeta_edicion, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    correo = tmp_path / "correo.txt"
    correo.write_text("Actividades del semestre.", encoding="utf-8")

    codigo = main(
        ["borrador", "2026-2", "--correo", str(correo), "--datos", str(carpeta_edicion.parent)]
    )

    assert codigo == 1
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
    assert not (carpeta_edicion / "borrador-sugerido.toml").exists()
