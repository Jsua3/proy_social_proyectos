# src/boletin_empleos/modelos.py
"""Modelos de dominio del boletín de empleos."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class Modalidad(StrEnum):
    PRESENCIAL = "presencial"
    HIBRIDO = "hibrido"
    REMOTO = "remoto"


class Decision(StrEnum):
    INCLUIR = "incluir"
    DESCARTAR = "descartar"


class MotivoDescarte(StrEnum):
    RELEVANCIA = "relevancia"
    EXPERIENCIA = "experiencia"
    VIGENCIA = "vigencia"
    ENLACE_MUERTO = "enlace_muerto"
    LEGITIMIDAD = "legitimidad"
    DUPLICADO = "duplicado"
    ES_PRACTICA = "es_practica"


class Oferta(BaseModel):
    """Una vacante ya normalizada, independiente de la fuente que la produjo."""

    id: str
    fuente: str
    titulo: str
    empresa: str | None = None
    ubicacion: str | None = None
    pais: str | None = None
    modalidad: Modalidad
    url: HttpUrl
    descripcion: str
    recogida_en: datetime

    fecha_publicacion: date | None = None
    fecha_vencimiento: date | None = None
    # La fuente garantiza que la vacante sigue abierta HOY. Lo ponen los
    # portales de empresa, que bajan el aviso cuando llenan el puesto; un
    # agregador no puede afirmarlo y deja este campo en False.
    vigencia_verificada: bool = False
    meses_experiencia: int | None = None
    es_practica: bool = False

    salario_min: int | None = None
    salario_max: int | None = None
    moneda: str | None = None

    @property
    def texto_completo(self) -> str:
        """Título y descripción concatenados, para puntuación de texto."""
        return f"{self.titulo}\n{self.descripcion}"


class Evaluacion(BaseModel):
    """El veredicto del núcleo sobre una oferta. `notas` se llena siempre."""

    oferta: Oferta
    puntaje_relevancia: float = Field(ge=0.0, le=1.0)
    puntaje_legitimidad: float = Field(ge=0.0, le=1.0)
    decision: Decision
    motivo: MotivoDescarte | None = None
    notas: list[str] = Field(default_factory=list)
    # Del eje cafetero. Ordena el boletín; nunca descarta.
    prioridad_local: bool = False
