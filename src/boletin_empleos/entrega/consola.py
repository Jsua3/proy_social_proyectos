"""Entrega de prueba: guarda el HTML en disco en vez de enviarlo. Usado por --dry-run."""

import logging
from datetime import UTC, datetime
from pathlib import Path

_log = logging.getLogger(__name__)


class EntregaConsola:
    def __init__(self, directorio: Path, nombre: str | None = None) -> None:
        self._directorio = Path(directorio)
        # El CLI la nombra por fecha para distinguirla de la edición completa que
        # queda en la misma carpeta. Sin nombre, marca de tiempo para no pisar nada.
        self._nombre = nombre

    def enviar(self, asunto: str, html: str, destinatarios: list[str]) -> bool:
        self._directorio.mkdir(parents=True, exist_ok=True)
        marca = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        ruta = self._directorio / (self._nombre or f"boletin-{marca}.html")
        ruta.write_text(html, encoding="utf-8")
        _log.info("boletín escrito en %s (destinatarios: %s)", ruta, ", ".join(destinatarios))
        return True
