"""Historial en JSON, commiteado al repositorio.

No se usa la caché de GitHub Actions: se borra a los 7 días sin uso, lo que la
vuelve inservible para un ciclo quincenal (spec §11).

Se escribe ordenado y con indentación para que los diffs en git sean legibles.

Un archivo que existe pero no se puede usar (JSON roto, bytes que no son UTF-8,
marcadores de conflicto de merge, forma inesperada) lanza HistorialIlegible y no
se toca. Partir de cero reenviaría todas las ofertas ya enviadas (spec §15.4) y el
siguiente registrar sobrescribiría el original; una ejecución fallida en Actions
es visible y no commitea nada (spec §12: degradación visible, nunca silenciosa).
"""

import json
import os
from datetime import date
from pathlib import Path

from boletin_empleos.almacenamiento.base import HistorialIlegible


def _forma_valida(datos: object) -> bool:
    """{"ediciones": [{"ids": [str, ...], ...}, ...]}. Lo demás no se adivina."""
    if not isinstance(datos, dict) or not isinstance(datos.get("ediciones"), list):
        return False
    return all(
        isinstance(ed, dict)
        and isinstance(ed.get("ids"), list)
        and all(isinstance(i, str) for i in ed["ids"])
        for ed in datos["ediciones"]
    )


class HistorialJSON:
    def __init__(self, ruta: Path) -> None:
        self._ruta = Path(ruta)
        self._datos = self._leer()

    def _leer(self) -> dict:
        if not self._ruta.exists():
            return {"ediciones": []}
        try:
            # utf-8-sig: el BOM que antepone el Bloc de notas no es corrupción.
            datos = json.loads(self._ruta.read_text("utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
            raise HistorialIlegible(f"historial ilegible en {self._ruta}: {e}") from e
        if not _forma_valida(datos):
            raise HistorialIlegible(
                f"historial con forma inesperada en {self._ruta}: se esperaba "
                '{"ediciones": [{"numero": ..., "fecha": ..., "ids": ["..."]}]}'
            )
        return datos

    def ids_enviados(self) -> set[str]:
        return {i for ed in self._datos["ediciones"] for i in ed["ids"]}

    def numero_edicion(self) -> int:
        return len(self._datos["ediciones"]) + 1

    def registrar(self, ids: set[str], fecha: date) -> None:
        self._datos["ediciones"].append(
            {
                "numero": self.numero_edicion(),
                "fecha": fecha.isoformat(),
                "ids": sorted(ids),
            }
        )
        texto = json.dumps(self._datos, ensure_ascii=False, indent=2) + "\n"
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        # Atómica: si el job se cancela a mitad, queda el archivo anterior entero y
        # no uno truncado. newline="\n" evita CRLF al correr en Windows.
        temporal = self._ruta.with_name(self._ruta.name + ".tmp")
        temporal.write_text(texto, encoding="utf-8", newline="\n")
        os.replace(temporal, self._ruta)
