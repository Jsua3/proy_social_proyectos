# src/boletin_empleos/fuentes/comun.py
"""Utilidades compartidas por los adaptadores de fuente.

Existe para que la misma lógica no viva copiada en cada adaptador: las cuatro
fuentes entregan fechas en variantes de ISO 8601 y todas necesitan interpretarlas
igual.
"""

from datetime import date, datetime


def fecha_iso(valor: str | None) -> date | None:
    """Interpreta una fecha ISO 8601, con o sin sufijo `Z`. None si no se puede."""
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).date()
    except ValueError:
        return None
