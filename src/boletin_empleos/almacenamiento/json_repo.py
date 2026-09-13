"""Historial en JSON, commiteado al repositorio.

No se usa la caché de GitHub Actions: se borra a los 7 días sin uso, lo que la
vuelve inservible para un ciclo quincenal (spec §11).

Se escribe ordenado y con indentación para que los diffs en git sean legibles.
"""

import json
import logging
from datetime import date
from pathlib import Path

_log = logging.getLogger(__name__)


class HistorialJSON:
    def __init__(self, ruta: Path) -> None:
        self._ruta = Path(ruta)
        self._datos = self._leer()

    def _leer(self) -> dict:
        if not self._ruta.exists():
            return {"ediciones": []}
        try:
            return json.loads(self._ruta.read_text("utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            _log.error("historial ilegible en %s (%s); se parte de cero", self._ruta, e)
            return {"ediciones": []}

    def ids_enviados(self) -> set[str]:
        return {i for ed in self._datos.get("ediciones", []) for i in ed.get("ids", [])}

    def numero_edicion(self) -> int:
        return len(self._datos.get("ediciones", [])) + 1

    def registrar(self, ids: set[str], fecha: date) -> None:
        self._datos.setdefault("ediciones", []).append(
            {
                "numero": self.numero_edicion(),
                "fecha": fecha.isoformat(),
                "ids": sorted(ids),
            }
        )
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        self._ruta.write_text(
            json.dumps(self._datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
