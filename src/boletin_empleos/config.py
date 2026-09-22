"""Carga de la configuración. Todo lo ajustable vive en config.toml."""

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field


class Vocabulario(BaseModel):
    cargos: list[str] = Field(default_factory=list)
    tecnologias: list[str] = Field(default_factory=list)
    excluidos: list[str] = Field(default_factory=list)
    # Términos que no admiten flexión: nombres propios de tecnología que, al
    # recibir sufijo, chocan con palabras españolas reales (ver config.toml).
    sin_flexion: list[str] = Field(default_factory=list)


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


class ConfigFuentes(BaseModel):
    """De dónde saca sus vacantes cada carrera.

    `consultas_spe` es común a todas (remoto nacional y los departamentos del eje)
    y `cargos_spe` es lo propio del programa. Se concatenan: así añadir una carrera
    no obliga a repetir la estrategia de descarga entera.
    """

    usar: list[str] = Field(default_factory=lambda: ["spe", "magneto", "remotive", "remoteok"])
    consultas_spe: list[dict[str, str]] = Field(default_factory=list)
    cargos_spe: list[str] = Field(default_factory=list)
    rutas_magneto: list[str] = Field(default_factory=list)

    def consultas(self) -> list[dict[str, str]]:
        return [*self.consultas_spe, *({"cargo": cargo} for cargo in self.cargos_spe)]


class ConfigGeografia(BaseModel):
    """Qué es "cerca" para esta institución. Solo ordena; nunca descarta.

    `otros_departamentos` resuelve colisiones reales de nombres: Antioquia tiene
    un municipio llamado Armenia y otro llamado Caldas. Cuando la ubicación
    nombra un departamento, ese manda sobre el nombre del municipio.
    """

    departamentos: list[str] = Field(default_factory=list)
    municipios: list[str] = Field(default_factory=list)
    otros_departamentos: list[str] = Field(default_factory=list)


class ConfigSitio(BaseModel):
    """El sitio público donde se archiva cada edición completa.

    El correo solo lleva las vacantes más pertinentes y enlaza allá: el boletín
    entero ronda los 300 KB y Gmail recorta los mensajes de más de unos 102 KB.
    Sin `url_base` no hay dónde enlazar y el correo va completo, como antes.
    """

    url_base: str = ""
    vacantes_en_correo: int = Field(default=10, gt=0)


class Config(BaseModel):
    # Qué carrera es. `clave` nombra carpetas y URLs (datos/<clave>/, /<clave>/);
    # `programa` es el nombre que leen las personas.
    clave: str
    programa: str
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
    sitio: ConfigSitio = Field(default_factory=ConfigSitio)
    geografia: ConfigGeografia = Field(default_factory=ConfigGeografia)
    fuentes: ConfigFuentes = Field(default_factory=ConfigFuentes)


def cargar_config(ruta: Path) -> Config:
    """Carga la configuración de una carrera, con lo que herede de la base."""
    return Config(**_leer(Path(ruta)))


def _leer(ruta: Path) -> dict:
    with ruta.open("rb") as f:
        datos = tomllib.load(f)

    # `extiende` apunta a un archivo hermano con lo que comparten todas las
    # carreras: geografía, heurísticas antiestafa, umbrales y pesos.
    base = datos.pop("extiende", None)
    if not base:
        return datos
    return _fundir(_leer(ruta.parent / base), datos)


def _fundir(base: dict, encima: dict) -> dict:
    """Mezcla tabla por tabla. Una lista del programa REEMPLAZA la de la base:

    añadir un cargo no debe obligar a adivinar si se suma o se pisa."""
    resultado = dict(base)
    for clave, valor in encima.items():
        if isinstance(valor, dict) and isinstance(resultado.get(clave), dict):
            resultado[clave] = _fundir(resultado[clave], valor)
        else:
            resultado[clave] = valor
    return resultado
