# src/boletin_empleos/fuentes/keyrus.py
"""Keyrus — portal de empleo propio de la empresa.

Recomendado por la profesora el 24/09/2026. Es una consultora de datos y
tecnología con operación en Colombia, así que sus vacantes le sirven sobre todo
a Ingeniería de Software, y alguna de consultoría a Ingeniería Industrial.

Base de permiso, verificada el 24/09/2026:
  · `robots.txt` solo prohíbe /app/, /messages/, /messenger/, /facebook/tab/ y
    /jobs/internal/. Las vacantes públicas están permitidas.
  · Declara `Content-Signal: search=yes, ai-train=no, ai-input=yes`. Este
    programa no entrena modelos con el contenido: lo lee para citarlo y
    enlazarlo, que es justo lo que esa señal permite.
  · No se raspa el HTML: el portal publica él mismo un feed JSON en /jobs.json,
    con el esquema JobPosting de schema.org dentro.

A diferencia de un agregador, un portal de empresa baja la vacante cuando la
llena. Por eso estas ofertas se marcan con `vigencia_verificada`: seguir
publicadas hoy ES la prueba de que siguen abiertas, y su fecha de publicación
—a veces de hace más de un año— no dice lo contrario.
"""

import logging
import re
from datetime import UTC, datetime

from boletin_empleos.fuentes.comun import fecha_iso
from boletin_empleos.http import crear_cliente, json_de, reintentar
from boletin_empleos.modelos import Modalidad, Oferta

_log = logging.getLogger(__name__)
_URL = "https://jobs.keyrus.co/jobs.json"

# "Cualquier ciudad en Colombia", "Cualquier Ciudad en México": el portal usa esta
# fórmula para las vacantes sin sede fija, que es como dice "remoto".
_SIN_SEDE = re.compile(r"^cualquier ciudad", re.IGNORECASE)

_PRACTICA = re.compile(r"\b(intern|interns|internship|practica|práctica|aprendiz)\b", re.IGNORECASE)

_ETIQUETAS = re.compile(r"<[^>]+>")


class FuenteKeyrus:
    nombre = "keyrus"
    base_permiso = (
        "Portal de empleo propio de la empresa. Su robots.txt permite las vacantes "
        "públicas y su Content-Signal declara search=yes y ai-input=yes; la lista se "
        "lee del feed JSON que el mismo portal publica, no del HTML."
    )
    atribucion = "Vacantes publicadas por Keyrus en su portal de empleo."
    url_atribucion = "https://jobs.keyrus.co/"
    # Alta: publica la propia empresa que contrata, no un intermediario.
    confianza_base = 0.90

    def __init__(self, url: str = _URL) -> None:
        self._url = url

    def obtener(self) -> list[Oferta]:
        with crear_cliente() as cliente:
            respuesta = reintentar(lambda: cliente.get(self._url).raise_for_status())
        if respuesta is None:
            _log.error("keyrus: no se pudo leer el feed de vacantes")
            return []

        datos = json_de(respuesta)
        if not isinstance(datos, dict):
            _log.error("keyrus: la respuesta no tiene la forma esperada")
            return []

        ahora = datetime.now(UTC)
        ofertas = []
        for bruto in datos.get("items", []):
            oferta = self._normalizar(bruto, ahora)
            if oferta is not None:
                ofertas.append(oferta)
        return ofertas

    def _normalizar(self, bruto: dict, ahora: datetime) -> Oferta | None:
        try:
            puesto = bruto.get("_jobposting") or {}
            titulo = bruto["title"]
            ubicacion, pais, remota = _lugar(puesto.get("jobLocation"))
            return Oferta(
                id=f"keyrus:{bruto['id']}",
                fuente=self.nombre,
                titulo=titulo,
                empresa="Keyrus",
                ubicacion=ubicacion,
                pais=pais,
                modalidad=Modalidad.REMOTO if remota else Modalidad.PRESENCIAL,
                url=bruto["url"],
                descripcion=_sin_etiquetas(puesto.get("description") or bruto.get("content_html")),
                recogida_en=ahora,
                fecha_publicacion=fecha_iso((bruto.get("date_published") or "")[:10]),
                es_practica=bool(_PRACTICA.search(titulo)),
                vigencia_verificada=True,
            )
        except (KeyError, ValueError) as e:
            _log.warning("keyrus: vacante descartada por dato inválido: %s", e)
            return None


def _lugar(lugares) -> tuple[str | None, str | None, bool]:
    """Devuelve (ubicación, país, ¿remota?). Entre varios países manda Colombia."""
    direcciones = [
        (lugar or {}).get("address") or {}
        for lugar in (lugares or [])
        if isinstance(lugar, dict | type(None))
    ]
    if not direcciones:
        return (None, None, False)

    elegida = next((d for d in direcciones if d.get("addressCountry") == "CO"), direcciones[0])
    ciudad = (elegida.get("addressLocality") or "").strip()
    region = (elegida.get("addressRegion") or elegida.get("streetAddress") or "").strip()

    if ciudad and _SIN_SEDE.match(ciudad):
        # "Cualquier ciudad en Colombia" -> remota, y la región ya nombra el país.
        return (region or ciudad, elegida.get("addressCountry"), True)

    partes = [p for p in (ciudad, region) if p]
    return (", ".join(partes) or None, elegida.get("addressCountry"), False)


def _sin_etiquetas(html: str | None) -> str:
    if not html:
        return ""
    return " ".join(_ETIQUETAS.sub(" ", html).split())
