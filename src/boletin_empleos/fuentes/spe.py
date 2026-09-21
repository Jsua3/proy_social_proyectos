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

from boletin_empleos.fuentes.comun import fecha_iso, limpiar_titulo, reparar_texto
from boletin_empleos.http import contexto_ssl, crear_cliente, json_de, reintentar
from boletin_empleos.modelos import Modalidad, Oferta
from boletin_empleos.nucleo.relevancia import normalizar_texto

_log = logging.getLogger(__name__)
_BASE = "https://www.buscadordeempleo.gov.co/backbue/v1"
_VERSION_ESPERADA = "2.4.0"

# El servidor del SPE envía solo su certificado de hoja y omite el intermedio
# GeoTrust TLS RSA CA G1. certifi trae la raíz (DigiCert Global Root G2) pero no
# ese intermedio, así que sin esto httpx falla con "unable to get local issuer
# certificate" y el adaptador devuelve cero ofertas en silencio.
# Verificado el 9/09/2026. La verificación TLS permanece activa.
INTERMEDIO_SPE = "geotrust-tls-rsa-ca-g1.pem"

# Estrategia de descarga medida en el spec §7: cubre remoto nacional, el mercado
# del eje cafetero, y ocupaciones de software a nivel nacional.
#
# Los tres departamentos del eje se consultan enteros —no solo por cargo— para
# alcanzar las vacantes locales cuyo título no usa ninguna de las palabras de
# abajo. Medido el 20/09/2026: Quindío 1.428 vacantes, Risaralda 6.207,
# Caldas 2.979. Cuesta unos minutos más de paginación por corrida; en un trabajo
# quincenal de un repositorio público, eso no cuesta nada.
#
# El nombre va SIN tilde: la API devuelve cero resultados con "Quindío".
CONSULTAS_POR_DEFECTO: list[dict[str, str]] = [
    {"teletrabajo": "1"},
    {"departamento": "Quindio"},
    {"departamento": "Risaralda"},
    {"departamento": "Caldas"},
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

        with crear_cliente(verificacion=contexto_ssl([INTERMEDIO_SPE])) as cliente:
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
        if version != _VERSION_ESPERADA:  # noqa: SIM102 — el log necesita ambos valores
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

            # Un JSON válido no garantiza tipos correctos. Sin estas comprobaciones,
            # `totalPages` como cadena, `resultados: null` o `resultados` como objeto
            # propagan TypeError/AttributeError fuera de obtener(), rompiendo el
            # contrato de que un adaptador nunca lanza.
            total = datos.get("totalPages", 1)
            total_paginas = total if isinstance(total, int) and total > 0 else 1

            resultados = datos.get("resultados")
            if not isinstance(resultados, list):
                _log.error("spe: 'resultados' no es una lista en %s p%d", consulta, pagina)
                return
            yield from (fila for fila in resultados if isinstance(fila, dict))
            pagina += 1
            if self._pausa:
                time.sleep(self._pausa)

    def _normalizar(self, bruto: dict, ahora: datetime) -> Oferta | None:
        try:
            codigo = str(bruto["CODIGO_VACANTE"])
            prestador, url = _prestador(bruto)
            prestador = reparar_texto(prestador)
            if not url:
                _log.debug("spe: vacante %s sin URL de detalle; se omite", codigo)
                return None

            minimo, maximo = _rango_salarial(bruto.get("RANGO_SALARIAL"))
            # Reparado ANTES de construir la Oferta: los filtros de relevancia y
            # experiencia deben ver el texto ya legible, no el mojibake (R2-1).
            municipio = reparar_texto((bruto.get("MUNICIPIO") or "").strip())
            departamento = reparar_texto((bruto.get("DEPARTAMENTO") or "").strip())
            titulo = limpiar_titulo(reparar_texto(bruto["TITULO_VACANTE"]))
            descripcion = reparar_texto(bruto.get("DESCRIPCION_VACANTE", ""))
            return Oferta(
                id=f"spe:{codigo}",
                fuente=self.nombre,
                titulo=titulo,
                empresa=prestador,
                ubicacion=_ubicacion(municipio, departamento),
                pais="CO",
                modalidad=_a_modalidad(bruto.get("TELETRABAJO")),
                url=url,
                descripcion=descripcion,
                recogida_en=ahora,
                fecha_publicacion=fecha_iso(bruto.get("FECHA_PUBLICACION")),
                fecha_vencimiento=fecha_iso(bruto.get("FECHA_VENCIMIENTO")),
                meses_experiencia=_meses_experiencia(bruto.get("MESES_EXPERIENCIA_CARGO")),
                es_practica=_a_booleano(bruto.get("PLAZA_PRACTICA")),
                salario_min=minimo,
                salario_max=maximo,
                moneda="COP" if minimo or maximo else None,
            )
        except (KeyError, ValueError, TypeError, AttributeError, IndexError) as e:
            _log.warning("spe: oferta descartada por dato inválido: %s", e)
            return None


def _ubicacion(municipio: str, departamento: str) -> str | None:
    """Combina municipio y departamento sin duplicar (R2-4).

    Evidencia real: `BOGOTÁ, D.C., BOGOTÁ, D.C.`, `DEPARTAMENTO CUNDINAMARCA,
    CUNDINAMARCA`. El SPE a veces repite el departamento dentro del propio
    municipio; se compara sin mayúsculas ni tildes con `normalizar_texto` del
    núcleo (un adaptador puede depender del núcleo, nunca al revés).
    """
    if not municipio:
        return departamento or None
    if not departamento or normalizar_texto(departamento) in normalizar_texto(municipio):
        return municipio
    return f"{municipio}, {departamento}"


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


# Algunas bolsas del SPE guardan MESES_EXPERIENCIA_CARGO como meses × 12.
# Evidencia real (valor del campo ↔ lo que dice la descripción de la vacante):
#   216 ↔ "18 meses de experiencia en cargos afines"
#   288 ↔ "24 meses de experiencia en cargos afines"
#   144 ↔ "12 meses de experiencia en cargos afines"
# mientras que 36 ↔ "3 años de experiencia" y 12 ↔ "un mínimo de un año" SÍ
# vienen en meses reales. En el primer boletín real, 29 de 60 descartes por
# experiencia tenían un valor > 120 y divisible entre 12 (16 de ellos "exige
# 144 meses"), incluida una vacante junior. Un valor de 120 o menos se deja
# igual: 72 o 96 podrían ser años reales y no hay forma de saberlo.
_UMBRAL_MESES_X_12 = 120


def _meses_experiencia(valor) -> int | None:
    entero = _entero(valor)
    if entero is not None and entero > _UMBRAL_MESES_X_12 and entero % 12 == 0:
        return entero // 12
    return entero


_NUMERO = re.compile(r"\$?\s*([\d.]{4,})")


def _rango_salarial(texto: str | None) -> tuple[int | None, int | None]:
    """Interpreta los rangos del SPE.

    Formatos reales: '$1.000.001 - $1.500.000', 'Mayor de $15.000.001', 'A Convenir'.
    """
    if not texto:
        return (None, None)
    numeros = [int(n.replace(".", "")) for n in _NUMERO.findall(texto)]
    if not numeros:
        return (None, None)
    if len(numeros) == 1:
        return (numeros[0], None)
    return (numeros[0], numeros[1])
