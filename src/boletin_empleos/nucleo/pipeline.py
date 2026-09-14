"""Orquestación del núcleo. Lógica pura: sin red, sin disco, sin reloj propio.

`hoy` se recibe por parámetro justamente para que las pruebas sean deterministas.
"""

from datetime import date

from pydantic import BaseModel, Field

from boletin_empleos.config import Config
from boletin_empleos.modelos import Decision, Evaluacion, MotivoDescarte, Oferta
from boletin_empleos.nucleo.deduplicacion import deduplicar
from boletin_empleos.nucleo.experiencia import experiencia_apropiada
from boletin_empleos.nucleo.legitimidad import puntuar_legitimidad
from boletin_empleos.nucleo.relevancia import puntuar_relevancia
from boletin_empleos.nucleo.vigencia import esta_vigente

_UMBRAL_LEGITIMIDAD = 0.45


class ResultadoEvaluacion(BaseModel):
    incluidas: list[Evaluacion] = Field(default_factory=list)
    descartadas: list[Evaluacion] = Field(default_factory=list)
    conteos: dict[str, int] = Field(default_factory=dict)


def evaluar(
    ofertas: list[Oferta],
    ya_enviadas: set[str],
    cfg: Config,
    confianza_por_fuente: dict[str, float],
    hoy: date,
) -> ResultadoEvaluacion:
    conteos = {
        "recibidas": len(ofertas),
        "ya_enviadas": 0,
        "duplicadas": 0,
        "descartadas_relevancia": 0,
        "descartadas_experiencia": 0,
        "descartadas_vigencia": 0,
        "descartadas_legitimidad": 0,
        "descartadas_practica": 0,
        "incluidas": 0,
    }

    nuevas = [o for o in ofertas if o.id not in ya_enviadas]
    conteos["ya_enviadas"] = len(ofertas) - len(nuevas)

    unicas, duplicadas = deduplicar(nuevas, confianza_por_fuente)
    conteos["duplicadas"] = len(duplicadas)

    incluidas: list[Evaluacion] = []
    descartadas: list[Evaluacion] = []

    for oferta in unicas:
        relevancia = puntuar_relevancia(oferta, cfg.vocabulario, cfg.relevancia)
        confianza = confianza_por_fuente.get(oferta.fuente, 0.5)
        legitimidad, notas_legitimidad = puntuar_legitimidad(oferta, confianza, cfg.legitimidad)

        def _descartar(
            motivo: MotivoDescarte,
            notas: list[str],
            _o=oferta,
            _r=relevancia,
            _l=legitimidad,
        ) -> None:
            # Los valores del bucle se ligan como argumentos por defecto: sin esto
            # ruff marca B023 (función que captura una variable de bucle).
            descartadas.append(
                Evaluacion(
                    oferta=_o,
                    puntaje_relevancia=_r,
                    puntaje_legitimidad=_l,
                    decision=Decision.DESCARTAR,
                    motivo=motivo,
                    notas=notas,
                )
            )

        if relevancia < cfg.umbral_relevancia:
            conteos["descartadas_relevancia"] += 1
            _descartar(MotivoDescarte.RELEVANCIA, [f"relevancia {relevancia:.2f}"])
            continue

        if cfg.excluir_practicas and oferta.es_practica:
            conteos["descartadas_practica"] += 1
            _descartar(MotivoDescarte.ES_PRACTICA, ["es plaza de práctica, no empleo"])
            continue

        apropiado, motivo_experiencia = experiencia_apropiada(
            oferta, cfg.experiencia, cfg.max_meses_experiencia
        )
        if not apropiado:
            conteos["descartadas_experiencia"] += 1
            _descartar(MotivoDescarte.EXPERIENCIA, [motivo_experiencia])
            continue

        vigente, motivo_vigencia = esta_vigente(oferta, hoy, cfg.dias_max_antiguedad)
        if not vigente:
            conteos["descartadas_vigencia"] += 1
            _descartar(MotivoDescarte.VIGENCIA, [motivo_vigencia])
            continue

        if legitimidad < _UMBRAL_LEGITIMIDAD:
            conteos["descartadas_legitimidad"] += 1
            _descartar(MotivoDescarte.LEGITIMIDAD, notas_legitimidad)
            continue

        incluidas.append(
            Evaluacion(
                oferta=oferta,
                puntaje_relevancia=relevancia,
                puntaje_legitimidad=legitimidad,
                decision=Decision.INCLUIR,
                notas=notas_legitimidad,
            )
        )

    incluidas.sort(key=lambda e: (e.puntaje_relevancia, e.puntaje_legitimidad), reverse=True)
    conteos["incluidas"] = len(incluidas)
    return ResultadoEvaluacion(incluidas=incluidas, descartadas=descartadas, conteos=conteos)
