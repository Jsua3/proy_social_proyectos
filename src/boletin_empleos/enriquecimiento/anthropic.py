# src/boletin_empleos/enriquecimiento/anthropic.py
"""Enriquecimiento con Claude. Degradable: ante cualquier fallo cae a nulo.

No decide qué ofertas entran — solo redacta. Es la invariante del spec §10.
"""

import json
import logging

from boletin_empleos.enriquecimiento.nulo import EnriquecedorNulo
from boletin_empleos.modelos import Evaluacion

_log = logging.getLogger(__name__)
_MODELO = "claude-sonnet-5"
_NULO = EnriquecedorNulo()


class EnriquecedorAnthropic:
    def __init__(self, api_key: str, modelo: str = _MODELO) -> None:
        self._api_key = api_key
        self._modelo = modelo

    def _pedir(self, prompt: str, max_tokens: int) -> str:
        from anthropic import Anthropic

        cliente = Anthropic(api_key=self._api_key)
        respuesta = cliente.messages.create(
            model=self._modelo,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return respuesta.content[0].text

    def resumir(self, evaluaciones: list[Evaluacion]) -> dict[str, str]:
        if not evaluaciones:
            return {}
        entradas = [
            {
                "id": e.oferta.id,
                "titulo": e.oferta.titulo,
                "descripcion": e.oferta.descripcion[:800],
            }
            for e in evaluaciones
        ]
        prompt = (
            "Resume cada vacante en UNA sola frase en español, máximo 20 palabras, "
            "enfocada en qué hace la persona y qué tecnologías usa. "
            "Responde SOLO un objeto JSON {id: resumen}, sin texto adicional.\n\n"
            f"{json.dumps(entradas, ensure_ascii=False)}"
        )
        try:
            texto = self._pedir(prompt, max_tokens=2000)
            datos = json.loads(texto[texto.index("{") : texto.rindex("}") + 1])
            return {str(k): str(v) for k, v in datos.items()}
        except Exception as e:
            _log.warning("enriquecimiento: falló el resumen (%s); el boletín sale sin resúmenes", e)
            return {}

    def editorial(self, evaluaciones: list[Evaluacion], conteos: dict[str, int]) -> str:
        prompt = (
            "Escribe un párrafo de apertura para un boletín quincenal de empleos dirigido a "
            "egresados de Ingeniería de Software de una universidad en Armenia, Quindío, Colombia. "
            "Máximo 60 palabras, tono institucional y sobrio, sin saludos ni despedidas. "
            f"Esta edición trae {conteos.get('incluidas', 0)} vacantes. "
            "Títulos incluidos: "
            f"{[e.oferta.titulo for e in evaluaciones[:10]]}"
        )
        try:
            return self._pedir(prompt, max_tokens=300).strip()
        except Exception as e:
            _log.warning("enriquecimiento: falló el editorial (%s); se usa el texto fijo", e)
            return _NULO.editorial(evaluaciones, conteos)
