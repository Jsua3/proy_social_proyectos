# src/boletin_empleos/http.py
"""Cliente HTTP compartido. Identifica al agente y reintenta con retroceso."""

import logging
import time
from collections.abc import Callable

import httpx

USER_AGENT = (
    "BoletinEmpleosCUE/1.0 "
    "(+https://github.com/Jsua3/proy_social_proyectos; coorproyeccioning@cue.edu.co)"
)

_log = logging.getLogger(__name__)


def crear_cliente(timeout: float = 30.0, acepta: str = "application/json") -> httpx.Client:
    """`acepta` se parametriza porque no todas las fuentes sirven JSON: Magneto sirve HTML
    y un servidor estricto respondería 406 ante un Accept que no puede satisfacer."""
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": acepta},
        timeout=timeout,
        follow_redirects=True,
    )


def reintentar[T](
    operacion: Callable[[], T], intentos: int = 3, espera_base: float = 1.0
) -> T | None:
    """Ejecuta `operacion` con retroceso exponencial. Devuelve None si todo falla."""
    for intento in range(intentos):
        try:
            return operacion()
        except (httpx.HTTPError, httpx.HTTPStatusError) as e:
            _log.warning("intento %d/%d falló: %s", intento + 1, intentos, e)
            if intento < intentos - 1:
                time.sleep(espera_base * (2**intento))
    return None
