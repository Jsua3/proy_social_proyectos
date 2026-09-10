# src/boletin_empleos/fuentes/spe.py
"""Servicio Público de Empleo — Ministerio del Trabajo de Colombia.

Fuente estatal: agrega las vacantes de todas las bolsas autorizadas del país.
`robots.txt` permisivo y publicación de datos abiertos.

API verificada el 9 de septiembre de 2026 (spec §7). No es una API pública
versionada contractualmente: `GET /version` se consulta en cada corrida para
detectar cambios de contrato.
"""

import logging
import re
import time
from datetime import UTC, datetime

from boletin_empleos.fuentes.comun import fecha_iso
from boletin_empleos.http import crear_cliente, json_de, reintentar
from boletin_empleos.modelos import Modalidad, Oferta

_log = logging.getLogger(__name__)
_BASE = "https://www.buscadordeempleo.gov.co/backbue/v1"
_VERSION_ESPERADA = "2.4.0"

# Estrategia de descarga medida en el spec §7: cubre remoto nacional,
# el mercado local del Quindío, y ocupaciones de software a nivel nacional.
CONSULTAS_POR_DEFECTO: list[dict[str, str]] = [
    {"teletrabajo": "1"},
    {"departamento": "Quindio"},
    {"cargo": "ingeniero de sistemas"},
    {"cargo": "desarrollador"},
    {"cargo": "programador"},
    {"cargo": "analista de sistemas"},
    {"cargo": "ingeniero de software"},
]


class FuenteSPE:
    nombre = "spe"
    base_permiso = (
        "Portal estatal del Ministerio del Trabajo; robots.txt permisivo "
        "y publicación de datos abiertos."
    )
    atribucion = "Vacantes del Servicio Público de Empleo (Ministerio del Trabajo de Colombia)."
    url_atribucion = "https://www.serviciodeempleo.gov.co/"
    confianza_base = 0.95

    def __init__(
        self,
        consultas: list[dict[str, str]] | None = None,
        max_paginas: int = 60,
        pausa: float = 0.5,
    ) -> None:
        self._consultas = consultas if consultas is not None else CONSULTAS_POR_DEFECTO
        self._max_paginas = max_paginas
        self._pausa = pausa

    def obtener(self) -> list[Oferta]:
        ahora = datetime.now(UTC)
        vistos: set[str] = set()
        ofertas: list[Oferta] = []

        with crear_cliente() as cliente:
            self._verificar_version(cliente)
            for consulta in self._consultas:
                for bruto in self._recorrer(cliente, consulta):
                    codigo = str(bruto.get("CODIGO_VACANTE", ""))
                    if not codigo or codigo in vistos:
                        continue
                    vistos.add(codigo)
                    oferta = self._normalizar(bruto, ahora)
                    if oferta is not None:
                        ofertas.append(oferta)
        return ofertas

    def _verificar_version(self, cliente) -> None:
        respuesta = reintentar(lambda: cliente.get(f"{_BASE}/version").raise_for_status())
        if respuesta is None:
            return
        datos = json_de(respuesta)
        if not isinstance(datos, dict):
            return
        version = datos.get("backVersion")
        if version != _VERSION_ESPERADA:
            _log.warning(
                "spe: la API cambió de versión (esperada %s, encontrada %s). "
                "Revisar el contrato del adaptador.",
                _VERSION_ESPERADA,
                version,
            )

    def _recorrer(self, cliente, consulta: dict[str, str]):
        pagina = 1
        total_paginas = 1
        while pagina <= min(total_paginas, self._max_paginas):
            params = consulta | {"page": str(pagina)}
            # `params=params` se liga como argumento por defecto: sin esto ruff marca B023
            # (función que captura una variable de bucle).
            respuesta = reintentar(
                lambda p=params: cliente.get(
                    f"{_BASE}/vacantes/resultados", params=p
                ).raise_for_status()
            )
            if respuesta is None:
                _log.error("spe: falló la consulta %s en la página %d", consulta, pagina)
                return
            datos = json_de(respuesta)
            if not isinstance(datos, dict):
                _log.error("spe: respuesta sin la forma esperada en %s p%d", consulta, pagina)
                return
            total_paginas = datos.get("totalPages", 1)
            yield from datos.get("resultados", [])
            pagina += 1
            if self._pausa:
                time.sleep(self._pausa)

    def _normalizar(self, bruto: dict, ahora: datetime) -> Oferta | None:
        try:
            codigo = str(bruto["CODIGO_VACANTE"])
            prestador, url = _prestador(bruto)
            if not url:
                _log.debug("spe: vacante %s sin URL de detalle; se omite", codigo)
                return None

            minimo, maximo = _rango_salarial(bruto.get("RANGO_SALARIAL"))
            municipio = (bruto.get("MUNICIPIO") or "").strip()
            departamento = (bruto.get("DEPARTAMENTO") or "").strip()
            return Oferta(
                id=f"spe:{codigo}",
                fuente=self.nombre,
                titulo=bruto["TITULO_VACANTE"],
                empresa=prestador,
                ubicacion=", ".join(p for p in (municipio, departamento) if p) or None,
                pais="CO",
                modalidad=_a_modalidad(bruto.get("TELETRABAJO")),
                url=url,
                descripcion=bruto.get("DESCRIPCION_VACANTE", ""),
                recogida_en=ahora,
                fecha_publicacion=fecha_iso(bruto.get("FECHA_PUBLICACION")),
                fecha_vencimiento=fecha_iso(bruto.get("FECHA_VENCIMIENTO")),
                meses_experiencia=_entero(bruto.get("MESES_EXPERIENCIA_CARGO")),
                es_practica=_a_booleano(bruto.get("PLAZA_PRACTICA")),
                salario_min=minimo,
                salario_max=maximo,
                moneda="COP" if minimo or maximo else None,
            )
        except (KeyError, ValueError, TypeError, AttributeError, IndexError) as e:
            _log.warning("spe: oferta descartada por dato inválido: %s", e)
            return None


def _prestador(bruto: dict) -> tuple[str | None, str | None]:
    """Extrae (nombre de la bolsa, URL de la vacante) de `DETALLES_PRESTADOR`.

    `DETALLES_PRESTADOR` es una LISTA de diccionarios, no una cadena. Verificado el
    9/09/2026: las 50 filas de una página traen exactamente un prestador, y las 50
    traen `URL_DETALLE_VACANTE`.

    El SPE no expone el empleador real: `NOMBRE_PRESTADOR` es la bolsa de empleo
    autorizada que publicó la vacante (Magneto, Comfenalco, Computrabajo…). Se usa
    igualmente como `empresa` porque es una entidad real, registrada ante el
    Ministerio, y porque dejarlo en None penalizaría sistemáticamente a la fuente
    más confiable del sistema en el filtro de legitimidad.
    """
    detalles = bruto.get("DETALLES_PRESTADOR")
    if not isinstance(detalles, list) or not detalles:
        return (None, None)
    primero = detalles[0]
    if not isinstance(primero, dict):
        return (None, None)
    nombre = (primero.get("NOMBRE_PRESTADOR") or "").strip() or None
    url = (primero.get("URL_DETALLE_VACANTE") or "").strip() or None
    return (nombre, url)


_VERDADEROS = {"1", "si", "sí", "true", "s", "y"}


def _a_modalidad(valor) -> Modalidad:
    if valor is None:
        return Modalidad.PRESENCIAL
    return Modalidad.REMOTO if str(valor).strip().lower() in _VERDADEROS else Modalidad.PRESENCIAL


def _a_booleano(valor) -> bool:
    return valor is not None and str(valor).strip().lower() in _VERDADEROS


def _entero(valor) -> int | None:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


_NUMERO = re.compile(r"\$?\s*([\d.]{4,})")


def _rango_salarial(texto: str | None) -> tuple[int | None, int | None]:
    """Interpreta los rangos del SPE.

    Ejemplos reales: '$1.000.001 - $1.500.000', 'Mayor de $15.000.001', 'A Convenir'.
    """
    if not texto:
        return (None, None)
    numeros = [int(n.replace(".", "")) for n in _NUMERO.findall(texto)]
    if not numeros:
        return (None, None)
    if len(numeros) == 1:
        return (numeros[0], None)
    return (numeros[0], numeros[1])
