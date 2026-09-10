# src/boletin_empleos/http.py
"""Cliente HTTP compartido. Identifica al agente y reintenta con retroceso."""

import json
import logging
import ssl
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import certifi
import httpx

USER_AGENT = (
    "BoletinEmpleosCUE/1.0 "
    "(+https://github.com/Jsua3/proy_social_proyectos; coorproyeccioning@cue.edu.co)"
)

_log = logging.getLogger(__name__)

_DIR_CERTIFICADOS = Path(__file__).parent / "certificados"


def contexto_ssl(intermedios: list[str]) -> ssl.SSLContext:
    """Contexto TLS de `certifi` más los certificados intermedios indicados.

    Algunos servidores envían una cadena TLS incompleta: omiten un intermedio y
    confían en que el cliente ya lo tenga. `certifi` trae las raíces, pero no
    compensa una cadena incompleta del servidor, así que sin el intermedio httpx
    falla con "unable to get local issuer certificate".

    Cargar un intermedio no baja la seguridad: `verify_mode` y `check_hostname`
    quedan en sus valores por defecto (ambos activos). `intermedios` son nombres
    de archivo dentro de `certificados/`, no rutas.
    """
    contexto = ssl.create_default_context(cafile=certifi.where())
    for nombre in intermedios:
        ruta = _DIR_CERTIFICADOS / nombre
        try:
            contexto.load_verify_locations(cadata=ruta.read_text("ascii"))
        except (OSError, ssl.SSLError) as e:
            _log.warning(
                "no se pudo cargar el certificado intermedio %s: %s. "
                "Si el emisor lo cambió, hay que reemplazarlo en certificados/.",
                nombre,
                e,
            )
    return contexto


def crear_cliente(
    tiempo_limite: float = 30.0,
    acepta: str = "application/json",
    verificacion: ssl.SSLContext | bool = True,
) -> httpx.Client:
    """`acepta` se parametriza porque no todas las fuentes sirven JSON: Magneto sirve HTML
    y un servidor estricto respondería 406 ante un Accept que no puede satisfacer.

    `verificacion` acepta un `ssl.SSLContext` (ver `contexto_ssl`) para fuentes cuyo
    servidor envía una cadena TLS incompleta; por defecto usa la verificación
    estándar de httpx con la verificación TLS activa.
    """
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": acepta},
        timeout=tiempo_limite,
        follow_redirects=True,
        verify=verificacion,
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
