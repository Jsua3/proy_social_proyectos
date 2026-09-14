"""Verificación de que los enlaces siguen vivos.

Hace red, por eso vive fuera del núcleo. Se corre solo sobre las ofertas que
ya pasaron los demás filtros: son pocas y el costo es bajo.

Criterio ante error de red: se conserva la oferta. Es peor perder una vacante
buena por un timeout que mostrar una dudosa.
"""

import logging

import httpx

from boletin_empleos.fuentes.spe import INTERMEDIO_SPE
from boletin_empleos.http import contexto_ssl, crear_cliente
from boletin_empleos.modelos import Decision, Evaluacion, MotivoDescarte

_log = logging.getLogger(__name__)


def filtrar_enlaces_vivos(
    evaluaciones: list[Evaluacion],
) -> tuple[list[Evaluacion], list[Evaluacion]]:
    """Devuelve (con enlace vivo, con enlace muerto)."""
    vivas: list[Evaluacion] = []
    muertas: list[Evaluacion] = []

    # El servidor del SPE omite el intermedio de su cadena TLS: sin él, todos sus
    # enlaces se darían por muertos y el boletín perdería las ofertas del SPE.
    # Accept */*: se verifican páginas HTML, no una API JSON.
    contexto = contexto_ssl([INTERMEDIO_SPE])
    with crear_cliente(tiempo_limite=15.0, acepta="*/*", verificacion=contexto) as cliente:
        for evaluacion in evaluaciones:
            if _responde(cliente, str(evaluacion.oferta.url)):
                vivas.append(evaluacion)
            else:
                muertas.append(
                    evaluacion.model_copy(
                        update={
                            "decision": Decision.DESCARTAR,
                            "motivo": MotivoDescarte.ENLACE_MUERTO,
                            "notas": [*evaluacion.notas, "el enlace ya no responde"],
                        }
                    )
                )
    return (vivas, muertas)


def _responde(cliente: httpx.Client, url: str) -> bool:
    for metodo in ("HEAD", "GET"):
        try:
            respuesta = cliente.request(metodo, url)
        except httpx.HTTPError as e:
            _log.warning("no se pudo verificar %s (%s); se conserva por prudencia", url, e)
            return True
        if respuesta.status_code < 400:
            return True
        if respuesta.status_code not in (405, 403):
            return False
    return False
