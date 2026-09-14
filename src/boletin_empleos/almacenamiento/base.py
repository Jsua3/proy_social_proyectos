"""Puerto de salida: persistencia del historial de envíos."""

from datetime import date
from typing import Protocol


class HistorialIlegible(Exception):
    """El historial existe pero no se puede usar: corrupto, mal codificado o con otra forma.

    Nunca se trata como historial vacío: eso reenviaría todas las ofertas ya enviadas
    (spec §15.4). El orquestador no la captura: la ejecución falla y no se commitea nada.
    """


class Historial(Protocol):
    def ids_enviados(self) -> set[str]:
        """IDs de todas las ofertas ya enviadas en cualquier edición previa."""
        ...

    def registrar(self, ids: set[str], fecha: date) -> None:
        """Añade una edición al historial."""
        ...

    def numero_edicion(self) -> int:
        """Número que le corresponde a la próxima edición (la primera es 1)."""
        ...
