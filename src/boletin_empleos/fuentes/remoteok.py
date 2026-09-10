# src/boletin_empleos/fuentes/remoteok.py
"""RemoteOK — API pública gratuita.

Condición legal textual: "Please link back (with follow, and without nofollow!)
to the URL on Remote OK and mention Remote OK as a source." No usar su logo:
es marca registrada.

El primer elemento del arreglo es el aviso legal, no una oferta.
"""

import logging
from datetime import UTC, datetime

from boletin_empleos.fuentes.comun import fecha_iso
from boletin_empleos.http import crear_cliente, json_de, reintentar
from boletin_empleos.modelos import Modalidad, Oferta

_log = logging.getLogger(__name__)
_URL = "https://remoteok.com/api"


class FuenteRemoteOK:
    nombre = "remoteok"
    base_permiso = "API pública gratuita, sin autenticación, con obligación de atribución."
    atribucion = "Ofertas remotas provistas por Remote OK."
    url_atribucion = "https://remoteok.com/"
    confianza_base = 0.70

    def obtener(self) -> list[Oferta]:
        with crear_cliente() as cliente:
            respuesta = reintentar(lambda: cliente.get(_URL).raise_for_status())
        if respuesta is None:
            _log.error("remoteok: no se pudo obtener la lista de ofertas")
            return []

        datos = json_de(respuesta)
        if not isinstance(datos, list):
            _log.error("remoteok: la respuesta no tiene la forma esperada")
            return []

        ahora = datetime.now(UTC)
        ofertas: list[Oferta] = []
        for bruto in datos:
            if "legal" in bruto:  # aviso legal, no es una oferta
                continue
            oferta = self._normalizar(bruto, ahora)
            if oferta is not None:
                ofertas.append(oferta)
        return ofertas

    def _normalizar(self, bruto: dict, ahora: datetime) -> Oferta | None:
        try:
            return Oferta(
                id=f"remoteok:{bruto['id']}",
                fuente=self.nombre,
                titulo=bruto["position"],
                empresa=bruto.get("company"),
                ubicacion=bruto.get("location") or "Remoto",
                pais=None,
                modalidad=Modalidad.REMOTO,
                url=bruto["url"],
                descripcion=bruto.get("description", ""),
                recogida_en=ahora,
                fecha_publicacion=fecha_iso(bruto.get("date")),
                salario_min=bruto.get("salary_min") or None,
                salario_max=bruto.get("salary_max") or None,
                moneda="USD" if bruto.get("salary_min") else None,
            )
        except (KeyError, ValueError) as e:
            _log.warning("remoteok: oferta descartada por dato inválido: %s", e)
            return None
