"""Carga de la configuración. Todo lo ajustable vive en config.toml."""

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field


class Vocabulario(BaseModel):
    cargos: list[str] = Field(default_factory=list)
    tecnologias: list[str] = Field(default_factory=list)
    excluidos: list[str] = Field(default_factory=list)


class PesosRelevancia(BaseModel):
    """Cómo se pondera una coincidencia al puntuar relevancia.

    Vive en config.toml, no incrustado en Python: estos números deciden si una
    oferta supera el umbral, y afinar el filtro no debe exigir saber programar.
    """

    peso_titulo: float = Field(default=0.7, ge=0.0, le=1.0)
    peso_descripcion: float = Field(default=0.3, ge=0.0, le=1.0)
    saturacion_base: float = Field(default=0.6, gt=0.0, le=1.0)
    saturacion_incremento: float = Field(default=0.2, ge=0.0, le=1.0)


class ConfigExperiencia(BaseModel):
    terminos_excluidos: list[str] = Field(default_factory=list)


class UmbralesLegitimidad(BaseModel):
    min_caracteres_descripcion: int = 200
    salario_minimo_legal: int = 1_623_500
    salario_maximo_razonable: int = 25_000_000
    frases_descarte: list[str] = Field(default_factory=list)
    frases_sospechosas: list[str] = Field(default_factory=list)
    dominios_sospechosos: list[str] = Field(default_factory=list)


class Config(BaseModel):
    destinatarios: list[str]
    remitente: str
    asunto: str
    umbral_relevancia: float = Field(gt=0.0, le=1.0)
    dias_max_antiguedad: int = Field(gt=0)
    max_meses_experiencia: int = 60
    excluir_practicas: bool = True
    relevancia: PesosRelevancia = Field(default_factory=PesosRelevancia)
    vocabulario: Vocabulario = Field(default_factory=Vocabulario)
    experiencia: ConfigExperiencia = Field(default_factory=ConfigExperiencia)
    legitimidad: UmbralesLegitimidad = Field(default_factory=UmbralesLegitimidad)


def cargar_config(ruta: Path) -> Config:
    with ruta.open("rb") as f:
        return Config(**tomllib.load(f))
