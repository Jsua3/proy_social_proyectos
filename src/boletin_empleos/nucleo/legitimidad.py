"""Heurísticas antiestafa. Lógica pura.

Parten de la confianza base de la fuente y restan según señales observadas.
Todas las listas de frases y dominios viven en config.toml para poder
ajustarlas sin tocar código (spec §8.4).
"""

from boletin_empleos.config import UmbralesLegitimidad
from boletin_empleos.modelos import Oferta
from boletin_empleos.nucleo.relevancia import normalizar_texto

_PENALIZACION_FUERTE = 0.40
_PENALIZACION_MEDIA = 0.25
_PENALIZACION_LEVE = 0.10

_MENSAJERIA = ("whatsapp", "telegram", "wasap", "wpp")


def puntuar_legitimidad(
    oferta: Oferta, confianza_base: float, cfg: UmbralesLegitimidad
) -> tuple[float, list[str]]:
    """Devuelve (puntaje 0.0–1.0, notas). 0.0 significa descarte inmediato."""
    texto = normalizar_texto(f"{oferta.titulo} {oferta.descripcion}")
    # Se compara contra el HOST, no contra la URL entera: "t.me" es subcadena de
    # export.media o de smart.mercadolibre.com, y por subcadena restaría 0.40 a
    # ofertas legítimas. `HttpUrl.host` da el host sin depender de módulos que el
    # núcleo tiene prohibidos.
    host = (oferta.url.host or "").lower()
    notas: list[str] = []

    # --- Señales de descarte inmediato ---
    for frase in cfg.frases_descarte:
        if normalizar_texto(frase) in texto:
            return (0.0, [f"pide dinero al aspirante: '{frase}'"])

    sin_empresa = not (oferta.empresa or "").strip()
    contacto_mensajeria = any(m in texto for m in _MENSAJERIA)
    if sin_empresa and contacto_mensajeria:
        return (0.0, ["sin empresa identificada y con contacto por mensajería personal"])

    # --- Penalizaciones ---
    puntaje = confianza_base

    if contacto_mensajeria:
        puntaje -= _PENALIZACION_FUERTE
        notas.append("el contacto es por mensajería personal")

    for dominio in cfg.dominios_sospechosos:
        if _es_el_host(host, dominio):
            puntaje -= _PENALIZACION_FUERTE
            notas.append(f"enlace hacia dominio sospechoso: {dominio}")
            break

    for frase in cfg.frases_sospechosas:
        if normalizar_texto(frase) in texto:
            puntaje -= _PENALIZACION_MEDIA
            notas.append(f"frase de captación: '{frase}'")
            break

    if sin_empresa:
        puntaje -= _PENALIZACION_MEDIA
        notas.append("sin empresa identificada")

    if _salario_fuera_de_rango(oferta, cfg):
        puntaje -= _PENALIZACION_MEDIA
        notas.append("salario fuera del rango razonable para el perfil")

    if len(oferta.descripcion.strip()) < cfg.min_caracteres_descripcion:
        puntaje -= _PENALIZACION_LEVE
        notas.append("descripción demasiado breve")

    return (round(max(0.0, min(1.0, puntaje)), 4), notas)


def _es_el_host(host: str, dominio: str) -> bool:
    """¿Es `dominio` el host de la oferta o un dominio padre suyo?

    `www.bit.ly` cuenta como `bit.ly`; `cutt.ly.empresa.co` no cuenta como `cutt.ly`,
    porque ahí el acortador es solo un rótulo dentro de un dominio ajeno.
    """
    dominio = dominio.lower().strip(".")
    return host == dominio or host.endswith("." + dominio)


def _salario_fuera_de_rango(oferta: Oferta, cfg: UmbralesLegitimidad) -> bool:
    """Solo se evalúa en pesos colombianos: un salario en USD es normal en remoto."""
    if oferta.moneda != "COP":
        return False
    if oferta.salario_min is not None and oferta.salario_min > cfg.salario_maximo_razonable:
        return True
    return oferta.salario_max is not None and 0 < oferta.salario_max < cfg.salario_minimo_legal
