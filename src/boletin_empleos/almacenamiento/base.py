"""Puerto de salida: persistencia del historial de envíos."""

from datetime import date
from typing import Protocol


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
