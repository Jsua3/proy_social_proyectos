# src/boletin_empleos/fuentes/remotive.py
"""Remotive — API pública gratuita.

Condición legal textual de su API: "Please link back to the URL found on
Remotive AND mention Remotive as a source... If you don't do that, we'll
terminate your API access." Las ofertas vienen con 24 h de retraso por diseño suyo.
"""

import logging
from datetime import UTC, datetime

from boletin_empleos.fuentes.comun import fecha_iso
from boletin_empleos.http import crear_cliente, json_de, reintentar
from boletin_empleos.modelos import Modalidad, Oferta

_log = logging.getLogger(__name__)
_URL = "https://remotive.com/api/remote-jobs"


class FuenteRemotive:
    nombre = "remotive"
    base_permiso = "API pública gratuita, sin autenticación, con obligación de atribución."
    atribucion = "Ofertas remotas provistas por Remotive."
    url_atribucion = "https://remotive.com/"
    confianza_base = 0.75

    def __init__(self, categoria: str = "software-dev", limite: int = 100) -> None:
        self._categoria = categoria
        self._limite = limite

    def obtener(self) -> list[Oferta]:
        with crear_cliente() as cliente:
            respuesta = reintentar(
                lambda: cliente.get(
                    _URL, params={"category": self._categoria, "limit": self._limite}
                ).raise_for_status()
            )
        if respuesta is None:
            _log.error("remotive: no se pudo obtener la lista de ofertas")
            return []

        datos = json_de(respuesta)
        if not isinstance(datos, dict):
            _log.error("remotive: la respuesta no tiene la forma esperada")
            return []

        ahora = datetime.now(UTC)
        ofertas: list[Oferta] = []
        for bruto in datos.get("jobs", []):
            oferta = self._normalizar(bruto, ahora)
            if oferta is not None:
                ofertas.append(oferta)
        return ofertas

    def _normalizar(self, bruto: dict, ahora: datetime) -> Oferta | None:
        try:
            return Oferta(
                id=f"remotive:{bruto['id']}",
                fuente=self.nombre,
                titulo=bruto["title"],
                empresa=bruto.get("company_name"),
                ubicacion=bruto.get("candidate_required_location"),
                pais=None,
                modalidad=Modalidad.REMOTO,
                url=bruto["url"],
                descripcion=bruto.get("description", ""),
                recogida_en=ahora,
                fecha_publicacion=fecha_iso(bruto.get("publication_date")),
            )
        except (KeyError, ValueError) as e:
            _log.warning("remotive: oferta descartada por dato inválido: %s", e)
            return None
