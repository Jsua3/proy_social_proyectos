# src/boletin_empleos/http.py
"""Cliente HTTP compartido. Identifica al agente y reintenta con retroceso."""

import json
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

USER_AGENT = (
    "BoletinEmpleosCUE/1.0 "
    "(+https://github.com/Jsua3/proy_social_proyectos; coorproyeccioning@cue.edu.co)"
)

_log = logging.getLogger(__name__)


def crear_cliente(tiempo_limite: float = 30.0, acepta: str = "application/json") -> httpx.Client:
    """`acepta` se parametriza porque no todas las fuentes sirven JSON: Magneto sirve HTML
    y un servidor estricto respondería 406 ante un Accept que no puede satisfacer."""
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": acepta},
        timeout=tiempo_limite,
        follow_redirects=True,
    )


def json_de(respuesta: httpx.Response) -> Any | None:
    """Interpreta el cuerpo como JSON. Devuelve None si no lo es.

    Un HTTP 200 no garantiza JSON: una página de mantenimiento, un interstitial de
    WAF o una respuesta truncada devuelven 200 con HTML. `respuesta.json()` lanzaría
    `JSONDecodeError` fuera del alcance de `reintentar` (que solo atrapa errores de
    transporte) y rompería el contrato de que un adaptador nunca lanza excepción.
    """
    try:
        return respuesta.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        _log.error(
            "respuesta de %s no es JSON válido (%s); se descarta la fuente en esta edición",
            respuesta.request.url if respuesta.request else "?",
            e,
        )
        return None


def reintentar[T](
    operacion: Callable[[], T], intentos: int = 3, espera_base: float = 1.0
) -> T | None:
    """Ejecuta `operacion` con retroceso exponencial. Devuelve None si todo falla.

    Genéricos con sintaxis PEP 695 (`def reintentar[T]`), no `TypeVar`: con
    `target-version = "py313"` la regla UP047 de ruff rechaza la forma antigua.
    """
    for intento in range(intentos):
        try:
            return operacion()
        except (httpx.HTTPError, httpx.HTTPStatusError) as e:
            _log.warning("intento %d/%d falló: %s", intento + 1, intentos, e)
            if intento < intentos - 1:
                time.sleep(espera_base * (2**intento))
    return None
