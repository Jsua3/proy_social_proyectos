"""Qué es una edición válida del boletín semestral y qué le falta para publicarse.

El archivo `edicion.toml` se valida contra estos modelos. Ningún campo admite
claves desconocidas: un error de dedo en un nombre de campo debe avisarse, no
ignorarse en silencio.
"""

from enum import StrEnum
from typing import Annotated, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

TIPOS_DE_SECCION = ("texto", "cifras", "proyectos", "comparativo", "videos", "imagen")


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Estado(StrEnum):
    BORRADOR = "borrador"
    APROBADA = "aprobada"


Porcentaje = Annotated[float, Field(ge=0, le=100)]


class Foto(_Modelo):
    archivo: str
    pie: str = ""


class Cifra(_Modelo):
    valor: str
    texto: str


class Proyecto(_Modelo):
    nombre: str
    docentes: list[str] = []
    programas: list[str] = []
    descripcion: str = ""
    foto: str | None = None


class Indicador(_Modelo):
    nombre: str
    anterior: Porcentaje
    actual: Porcentaje


class Grupo(_Modelo):
    nombre: str
    indicadores: list[Indicador] = []


class Video(_Modelo):
    titulo: str
    enlace: str
    miniatura: str | None = None

    @field_validator("enlace")
    @classmethod
    def _solo_https(cls, enlace: str) -> str:
        if not enlace.startswith("https://"):
            raise ValueError("el enlace del video debe empezar con https://")
        return enlace


class _Seccion(_Modelo):
    etiqueta: str
    titulo: str
    pendiente: str | None = None

    def tiene_contenido(self) -> bool:
        raise NotImplementedError

    def nombres_de_fotos(self) -> list[str]:
        return []


class SeccionTexto(_Seccion):
    tipo: Literal["texto"]
    cuerpo: str = ""
    fotos: list[Foto] = Field(default=[], max_length=3)

    def tiene_contenido(self) -> bool:
        return bool(self.cuerpo.strip())

    def nombres_de_fotos(self) -> list[str]:
        return [f.archivo for f in self.fotos]


class SeccionCifras(_Seccion):
    tipo: Literal["cifras"]
    cifras: list[Cifra] = Field(default=[], max_length=6)
    foto: str | None = None

    def tiene_contenido(self) -> bool:
        return bool(self.cifras)

    def nombres_de_fotos(self) -> list[str]:
        return [self.foto] if self.foto else []


class SeccionProyectos(_Seccion):
    tipo: Literal["proyectos"]
    proyectos: list[Proyecto] = []

    def tiene_contenido(self) -> bool:
        return bool(self.proyectos)

    def nombres_de_fotos(self) -> list[str]:
        return [p.foto for p in self.proyectos if p.foto]


class SeccionComparativo(_Seccion):
    tipo: Literal["comparativo"]
    periodo_anterior: str = ""
    periodo_actual: str = ""
    meta: Porcentaje | None = None
    grupos: list[Grupo] = []

    def tiene_contenido(self) -> bool:
        return any(g.indicadores for g in self.grupos)


class SeccionVideos(_Seccion):
    tipo: Literal["videos"]
    videos: list[Video] = []

    def tiene_contenido(self) -> bool:
        return bool(self.videos)

    def nombres_de_fotos(self) -> list[str]:
        return [v.miniatura for v in self.videos if v.miniatura]


class SeccionImagen(_Seccion):
    tipo: Literal["imagen"]
    archivo: str | None = None
    descripcion: str = ""

    def tiene_contenido(self) -> bool:
        return bool(self.archivo)

    def nombres_de_fotos(self) -> list[str]:
        return [self.archivo] if self.archivo else []


Seccion = Annotated[
    SeccionTexto
    | SeccionCifras
    | SeccionProyectos
    | SeccionComparativo
    | SeccionVideos
    | SeccionImagen,
    Field(discriminator="tipo"),
]


class Portada(_Modelo):
    titular: str = ""
    foto: str | None = None


class Editorial(_Modelo):
    titulo: str = ""
    cuerpo: str = ""
    firma: str = ""


class Contraportada(_Modelo):
    foto: str | None = None


class Edicion(_Modelo):
    volumen: int = Field(ge=1)
    semestre: str = Field(pattern=r"^\d{4}-[12]$")
    fecha: str
    estado: Estado = Estado.BORRADOR
    portada: Portada
    editorial: Editorial
    contraportada: Contraportada = Contraportada()
    secciones: list[Seccion]


class Pendiente(NamedTuple):
    lugar: str
    motivo: str


def antetitulo(indice: int, seccion: _Seccion) -> str:
    """El antetítulo numerado que va sobre el título: «04 · Planeta»."""
    return f"{indice + 1:02d} · {seccion.etiqueta}"


def pendientes(edicion: Edicion) -> list[Pendiente]:
    """Lo que le falta a la edición, en el orden en que aparece en el boletín."""
    resultado = []

    faltan_en_portada = []
    if not edicion.portada.titular.strip():
        faltan_en_portada.append("el titular")
    if not edicion.portada.foto:
        faltan_en_portada.append("la foto")
    if faltan_en_portada:
        resultado.append(Pendiente("Portada", "Falta " + " y ".join(faltan_en_portada)))

    if not edicion.editorial.cuerpo.strip():
        resultado.append(Pendiente("Editorial", "Falta el texto"))

    for indice, seccion in enumerate(edicion.secciones):
        lugar = f"{antetitulo(indice, seccion)} — {seccion.titulo}"
        if seccion.pendiente:
            resultado.append(Pendiente(lugar, seccion.pendiente))
        elif not seccion.tiene_contenido():
            resultado.append(Pendiente(lugar, "Sin contenido"))

    return resultado


def fotos_nombradas(edicion: Edicion) -> list[str]:
    """Todas las fotos que nombra la edición, sin repetir y en orden de aparición."""
    nombres = [edicion.portada.foto]
    for seccion in edicion.secciones:
        nombres.extend(seccion.nombres_de_fotos())
    nombres.append(edicion.contraportada.foto)
    return list(dict.fromkeys(n for n in nombres if n))
