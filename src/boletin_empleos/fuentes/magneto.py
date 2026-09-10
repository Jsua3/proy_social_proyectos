# src/boletin_empleos/fuentes/magneto.py
"""Magneto365 — portal de empleo colombiano.

Base de permiso: Magneto publica un `llms.txt` dirigido explícitamente a
asistentes de IA, con URLs canónicas de alta calidad y la instrucción
"Evitar URLs con parámetros". Su robots.txt lo confirma con `Disallow: /*?`.

Por eso este adaptador solo pide rutas canónicas y jamás añade query string.
"""

import logging
import time
from datetime import UTC, datetime

from selectolax.parser import HTMLParser

from boletin_empleos.http import crear_cliente, reintentar
from boletin_empleos.modelos import Modalidad, Oferta

_log = logging.getLogger(__name__)
_ORIGEN = "https://www.magneto365.com"

# Rutas canónicas del llms.txt de Magneto, VERIFICADAS el 9/09/2026 (todas HTTP 200).
# `/co/trabajos/ofertas-empleo-trabajo-remoto` se excluye a propósito: devuelve HTTP 500
# desde el servidor de Magneto, no por culpa de nuestro agente. Si lo arreglan, se añade.
RUTAS_POR_DEFECTO = [
    "/co/trabajos/buscar",
    "/co/trabajos/ofertas-empleo-en-bogota",
    "/co/trabajos/ofertas-empleo-en-medellin",
    "/co/trabajos/ofertas-empleo-en-pereira",
]

# Selectores verificados contra el HTML real de Magneto el 9/09/2026: cada vacante es un
# <article> que contiene un enlace a /co/empleos/<slug> y un <h2> con el título — 21 de 21
# tarjetas cumplen ambas condiciones. Deliberadamente NO se usan las clases
# `mg_job_card_desktop_magneto-ui-card-jobs_13c81`: llevan hash de CSS-modules y cambian
# en cada despliegue suyo.
_SEL_TARJETA = "article"
_SEL_ENLACE = 'a[href*="/co/empleos/"]'
_SEL_TITULO = "h2"

# El texto de la tarjeta viene segmentado de forma estable:
#   [0] título · [1] empresa · [2] tipo de contrato · [3] salario · [4] ubicación · [5] urgencia
_IDX_EMPRESA = 1
_IDX_UBICACION = 4
_MIN_SEGMENTOS, _MAX_SEGMENTOS = 4, 8


class FuenteMagneto:
    nombre = "magneto"
    base_permiso = (
        "Magneto publica un llms.txt dirigido a asistentes de IA con URLs canónicas; "
        "su robots.txt permite el sitio y prohíbe solo URLs con parámetros."
    )
    atribucion = "Ofertas del portal de empleo Magneto."
    url_atribucion = "https://www.magneto365.com/co"
    confianza_base = 0.80

    def __init__(self, rutas: list[str] | None = None, pausa: float = 1.0) -> None:
        self._rutas = rutas if rutas is not None else RUTAS_POR_DEFECTO
        self._pausa = pausa

    def obtener(self) -> list[Oferta]:
        ahora = datetime.now(UTC)
        vistos: set[str] = set()
        ofertas: list[Oferta] = []

        with crear_cliente(acepta="text/html,application/xhtml+xml") as cliente:
            for ruta in self._rutas:
                if "?" in ruta:
                    raise ValueError(f"Magneto prohíbe URLs con parámetros: {ruta}")
                # `r=ruta` se liga como argumento por defecto: sin esto ruff marca B023
                # (función que captura una variable de bucle).
                respuesta = reintentar(
                    lambda r=ruta: cliente.get(f"{_ORIGEN}{r}").raise_for_status()
                )
                if respuesta is None:
                    _log.error("magneto: no se pudo obtener %s", ruta)
                    continue
                for oferta in self._extraer(respuesta.text, ahora):
                    if oferta.id not in vistos:
                        vistos.add(oferta.id)
                        ofertas.append(oferta)
                if self._pausa:
                    time.sleep(self._pausa)
        return ofertas

    def _extraer(self, html: str, ahora: datetime):
        arbol = HTMLParser(html)
        for tarjeta in arbol.css(_SEL_TARJETA):
            enlace = tarjeta.css_first(_SEL_ENLACE)
            titulo = tarjeta.css_first(_SEL_TITULO)
            if enlace is None or titulo is None:
                continue

            href = enlace.attributes.get("href") or ""
            url = (href if href.startswith("http") else f"{_ORIGEN}{href}").split("?")[0]
            segmentos = _segmentos(tarjeta)
            try:
                yield Oferta(
                    id=f"magneto:{url.rstrip('/').rsplit('/', 1)[-1]}",
                    fuente=self.nombre,
                    titulo=titulo.text(strip=True),
                    empresa=_segmento(segmentos, _IDX_EMPRESA),
                    ubicacion=_segmento(segmentos, _IDX_UBICACION),
                    pais="CO",
                    modalidad=Modalidad.PRESENCIAL,
                    url=url,
                    descripcion=tarjeta.text(separator=" · ", strip=True)[:2000],
                    recogida_en=ahora,
                )
            except ValueError as e:
                _log.warning("magneto: tarjeta descartada: %s", e)


def _segmentos(tarjeta) -> list[str]:
    """Segmentos de texto de la tarjeta, solo si su número es el esperado.

    Una tarjeta con un número anómalo de segmentos no se descarta: conserva título y
    enlace, y deja empresa y ubicación en None. Es preferible una oferta con datos
    incompletos a perder la oferta.
    """
    partes = [p.strip() for p in tarjeta.text(separator="|", strip=True).split("|") if p.strip()]
    return partes if _MIN_SEGMENTOS <= len(partes) <= _MAX_SEGMENTOS else []


def _segmento(segmentos: list[str], indice: int) -> str | None:
    return segmentos[indice] if indice < len(segmentos) else None
