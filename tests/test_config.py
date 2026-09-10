from pathlib import Path

from boletin_empleos.config import cargar_config

RAIZ = Path(__file__).resolve().parents[1]


def test_carga_el_config_del_proyecto():
    cfg = cargar_config(RAIZ / "config.toml")

    assert cfg.destinatarios, "debe haber al menos un destinatario"
    assert cfg.vocabulario.cargos, "el vocabulario de cargos no puede estar vacío"
    assert cfg.vocabulario.tecnologias
    assert 0.0 < cfg.umbral_relevancia <= 1.0
    assert cfg.dias_max_antiguedad > 0
    assert cfg.legitimidad.frases_descarte
    assert cfg.legitimidad.min_caracteres_descripcion == 200


def test_los_terminos_del_vocabulario_estan_normalizados():
    cfg = cargar_config(RAIZ / "config.toml")
    todos = cfg.vocabulario.cargos + cfg.vocabulario.tecnologias
    assert all(t == t.lower().strip() for t in todos), (
        "deben venir en minúscula y sin espacios extra"
    )
