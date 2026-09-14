"""Puerto de salida: entrega del boletín.

Hoy hay un destinatario. Añadir la lista de egresados (fase 2) es añadir otro
adaptador detrás de este mismo puerto, sin tocar nada más.
"""

from typing import Protocol


class Entrega(Protocol):
    def enviar(self, asunto: str, html: str, destinatarios: list[str]) -> bool:
        """Devuelve True si se entregó. Nunca lanza excepción."""
        ...
