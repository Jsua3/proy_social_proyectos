"""Borrador opcional: Claude propone textos a partir del correo de la Coordinación.

Las propuestas van a `borrador-sugerido.toml`, aparte; el monitor copia lo que le
sirva. Este módulo nunca escribe `edicion.toml`, y ante cualquier fallo devuelve
None: el resto del programa funciona igual sin él (spec §10).
"""

import logging
from pathlib import Path

import tomli_w
from pydantic import BaseModel, ConfigDict

from boletin_semestral.modelo import Cifra, Edicion

_log = logging.getLogger(__name__)

MODELO = "claude-opus-5-5"


class _Esquema(BaseModel):
    # Todo obligatorio y sin claves extra: el esquema JSON se manda tal cual a Claude.
    model_config = ConfigDict(extra="forbid")


class ProyectoSugerido(_Esquema):
    nombre: str
    docentes: list[str]
    programas: list[str]
    descripcion: str


class Sugerencia(_Esquema):
    seccion: str
    cuerpo: str
    cifras: list[Cifra]
    proyectos: list[ProyectoSugerido]


class Sugerencias(_Esquema):
    sugerencias: list[Sugerencia]


class Redactor:
    def __init__(self, modelo: str = MODELO) -> None:
        self._modelo = modelo

    def _pedir(self, prompt: str) -> str:
        from anthropic import Anthropic

        respuesta = Anthropic().beta.messages.create(
            model=self._modelo,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={
                "format": {"type": "json_schema", "schema": Sugerencias.model_json_schema()}
            },
            messages=[{"role": "user", "content": prompt}],
        )
        if respuesta.stop_reason == "refusal":
            raise RuntimeError("Claude no aceptó la petición")
        return next(b.text for b in respuesta.content if b.type == "text")

    def proponer(self, correo: str, edicion: Edicion) -> Sugerencias | None:
        """Propone textos por sección. Devuelve None si algo falla; nunca lanza."""
        try:
            return Sugerencias.model_validate_json(self._pedir(_prompt(correo, edicion)))
        except Exception as e:
            _log.warning("borrador: no se pudo obtener una propuesta (%s)", e)
            return None


def _prompt(correo: str, edicion: Edicion) -> str:
    secciones = "\n".join(f"- {s.etiqueta}: {s.titulo.replace('*', '')}" for s in edicion.secciones)
    return f"""\
Ayudas a armar el boletín semestral de proyección social de la Facultad de Ingenierías y \
Ciencias Básicas de la Corporación Universitaria Empresarial Alexander von Humboldt \
(Armenia, Quindío). Edición: Vol. {edicion.volumen}, {edicion.fecha}.

Abajo va el correo en el que la Coordinación de Proyección Social cuenta las actividades \
del semestre. Propón el texto de cada sección del boletín a partir de ese correo.

Reglas:
- Usa solo lo que dice el correo: no inventes cifras, nombres, fechas ni logros.
- Asigna cada actividad a la sección cuya etiqueta encaje mejor; si ninguna encaja, usa \
la etiqueta Otras.
- Escribe en español, en tercera persona, con frases cortas.
- Pon en «cifras» solo números que aparezcan en el correo, y en «proyectos» solo los \
proyectos que el correo nombra, con sus docentes.

Secciones de esta edición (etiqueta: título):
{secciones}

Correo de la Coordinación:
<correo>
{correo}
</correo>
"""


def escribir_sugerencias(sugerencias: Sugerencias, destino: Path) -> None:
    """Guarda las propuestas como TOML, para copiarlas a mano a `edicion.toml`."""
    texto = tomli_w.dumps(sugerencias.model_dump())
    aviso = (
        "# Propuestas de Claude a partir del correo. NO se publican: copia a edicion.toml\n"
        "# lo que sirva y revisa cada dato contra el correo original.\n\n"
    )
    Path(destino).write_text(aviso + texto, encoding="utf-8")
