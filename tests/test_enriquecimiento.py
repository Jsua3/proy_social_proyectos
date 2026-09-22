# tests/test_enriquecimiento.py
from datetime import UTC, datetime

from boletin_empleos.enriquecimiento import crear_enriquecedor
from boletin_empleos.enriquecimiento.nulo import EnriquecedorNulo
from boletin_empleos.modelos import Decision, Evaluacion, Modalidad, Oferta


def _evaluacion() -> Evaluacion:
    return Evaluacion(
        oferta=Oferta(
            id="x:1",
            fuente="x",
            titulo="Desarrollador",
            modalidad=Modalidad.REMOTO,
            url="https://ejemplo.co/1",
            descripcion="Descripción larga de la vacante.",
            recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
        ),
        puntaje_relevancia=0.9,
        puntaje_legitimidad=0.9,
        decision=Decision.INCLUIR,
    )


def test_sin_api_key_se_usa_el_enriquecedor_nulo():
    assert isinstance(crear_enriquecedor(None), EnriquecedorNulo)
    assert isinstance(crear_enriquecedor(""), EnriquecedorNulo)


def test_el_enriquecedor_nulo_no_rompe_nada():
    e = EnriquecedorNulo()
    assert e.resumir([_evaluacion()]) == {}
    assert isinstance(e.editorial([_evaluacion()], {"incluidas": 1}), str)
    assert e.editorial([_evaluacion()], {"incluidas": 1}), "debe dar un texto fijo, no vacío"


def test_anthropic_cae_a_nulo_si_el_proveedor_falla(monkeypatch):
    from boletin_empleos.enriquecimiento.anthropic import EnriquecedorAnthropic

    e = EnriquecedorAnthropic(api_key="clave-falsa")

    def explotar(*args, **kwargs):
        raise RuntimeError("proveedor caído")

    monkeypatch.setattr(e, "_pedir", explotar)

    assert e.resumir([_evaluacion()]) == {}
    assert e.editorial([_evaluacion()], {"incluidas": 1})


def test_r2_6_el_editorial_fijo_no_afirma_que_son_de_las_ultimas_dos_semanas():
    """R2-6: la regla de vigencia deja entrar ofertas publicadas hace más de dos

    semanas (mientras no hayan vencido), así que el texto fijo no puede
    afirmar esa ventana de tiempo."""
    texto = EnriquecedorNulo().editorial([_evaluacion()], {"incluidas": 1})
    assert "últimas dos semanas" not in texto
    assert "quincena" not in texto.lower()
    assert "vigentes a la fecha" in texto


def test_r2_6_el_prompt_del_editorial_no_le_pide_al_modelo_que_mienta_sobre_la_ventana():
    """El prompt tampoco debe insinuarle al modelo una ventana de dos semanas o

    una quincena que la regla de vigencia no respeta."""
    from boletin_empleos.enriquecimiento.anthropic import EnriquecedorAnthropic

    capturado = {}

    def capturar(prompt, max_tokens):
        capturado["prompt"] = prompt
        return "editorial generado"

    e = EnriquecedorAnthropic(api_key="clave-falsa")
    e._pedir = capturar
    e.editorial([_evaluacion()], {"incluidas": 1})

    assert "quincenal" not in capturado["prompt"].lower()
    assert "últimas dos semanas" not in capturado["prompt"]
    assert "quincena" not in capturado["prompt"].lower()


# --- El encargo institucional que enmarca lo que el modelo escribe --------------


def test_el_contexto_dice_para_quien_y_para_que_es_el_boletin():
    from boletin_empleos.enriquecimiento.contexto import contexto_institucional

    texto = contexto_institucional("Ingeniería de Software").lower()
    for clave in (
        "proyección social",
        "egresados",
        "alexander von humboldt",
        "quindío",
        "eje cafetero",
        "empleabilidad",
    ):
        assert clave in texto, f"el encargo debe nombrar «{clave}»"


def test_el_editorial_le_pasa_el_encargo_al_modelo():
    from boletin_empleos.enriquecimiento.anthropic import EnriquecedorAnthropic

    capturado = {}

    def capturar(prompt, max_tokens):
        capturado["prompt"] = prompt
        return "editorial generado"

    e = EnriquecedorAnthropic(api_key="clave-falsa")
    e._pedir = capturar
    e.editorial([_evaluacion()], {"incluidas": 1})

    assert "Proyección Social" in capturado["prompt"]
    assert "egresados" in capturado["prompt"]


def test_el_resumen_le_prohibe_al_modelo_inventar():
    """Un resumen inventado se publica como si fuera de la oferta real."""
    from boletin_empleos.enriquecimiento.anthropic import EnriquecedorAnthropic

    capturado = {}

    def capturar(prompt, max_tokens):
        capturado["prompt"] = prompt
        return "{}"

    e = EnriquecedorAnthropic(api_key="clave-falsa")
    e._pedir = capturar
    e.resumir([_evaluacion()])

    assert "no inventes" in capturado["prompt"].lower()


def test_el_encargo_nombra_la_carrera_de_la_edicion():
    from boletin_empleos.enriquecimiento.contexto import contexto_institucional

    industrial = contexto_institucional("Ingeniería Industrial")

    assert "Ingeniería Industrial" in industrial
    assert "Ingeniería de Software" not in industrial
    assert "Proyección Social" in industrial, "el encargo sigue siendo el mismo"


def test_el_texto_fijo_no_habla_de_software_en_el_boletin_de_industrial():
    """Sin clave de IA el editorial sale del texto fijo: no puede nombrar la

    carrera equivocada."""
    texto = EnriquecedorNulo("Ingeniería Industrial").editorial([_evaluacion()], {"incluidas": 1})

    assert "software" not in texto.lower()
    assert "Ingeniería Industrial" in texto
    assert "vigentes a la fecha" in texto
