# src/boletin_empleos/enriquecimiento/__init__.py
"""Selección automática del enriquecedor según haya o no API key."""

from boletin_empleos.enriquecimiento.base import Enriquecedor
from boletin_empleos.enriquecimiento.nulo import EnriquecedorNulo


def crear_enriquecedor(api_key: str | None, programa: str = "") -> Enriquecedor:
    if not api_key:
        return EnriquecedorNulo(programa)
    from boletin_empleos.enriquecimiento.anthropic import EnriquecedorAnthropic

    return EnriquecedorAnthropic(api_key=api_key, programa=programa)


__all__ = ["Enriquecedor", "EnriquecedorNulo", "crear_enriquecedor"]
