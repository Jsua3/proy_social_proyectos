"""Render del boletín. MJML compila a HTML tolerante a clientes de correo.

El pie de atribución se construye recorriendo las fuentes que aportaron
ofertas: nunca se escribe a mano. Remotive y RemoteOK cortan el acceso si no
se les cita (spec §9).
"""

from datetime import date
from pathlib import Path

from jinja2_mjml import Environment
from pydantic import BaseModel, Field

from boletin_empleos.modelos import Evaluacion, Modalidad, MotivoDescarte, Oferta

_PLANTILLAS = Path(__file__).parent / "plantillas"

# Solo estos motivos llegan al apéndice del boletín (spec §8.6).
_MOTIVOS_VISIBLES = {
    MotivoDescarte.LEGITIMIDAD,
    MotivoDescarte.EXPERIENCIA,
    MotivoDescarte.VIGENCIA,
    MotivoDescarte.ENLACE_MUERTO,
}


class FuenteUsada(BaseModel):
    nombre: str
    atribucion: str
    url_atribucion: str


class DatosBoletin(BaseModel):
    numero_edicion: int
    fecha: date
    editorial: str
    incluidas: list[Evaluacion]
    descartadas: list[Evaluacion] = Field(default_factory=list)
    resumenes: dict[str, str] = Field(default_factory=dict)
    conteos: dict[str, int] = Field(default_factory=dict)
    fuentes_usadas: list[FuenteUsada] = Field(default_factory=list)
    fuentes_caidas: list[str] = Field(default_factory=list)


def renderizar(datos: DatosBoletin) -> str:
    entorno = Environment(loader=_cargador())
    plantilla = entorno.get_template("boletin.mjml")
    return plantilla.render(
        numero_edicion=datos.numero_edicion,
        fecha=datos.fecha.isoformat(),
        editorial=datos.editorial,
        conteos=datos.conteos,
        secciones=_agrupar(datos),
        descartes_visibles=[
            _con_extras(e, datos) for e in datos.descartadas if e.motivo in _MOTIVOS_VISIBLES
        ],
        fuentes_usadas=datos.fuentes_usadas,
        fuentes_caidas=datos.fuentes_caidas,
    )


def _cargador():
    from jinja2 import FileSystemLoader

    return FileSystemLoader(str(_PLANTILLAS))


class _Adornada(BaseModel):
    """Una evaluación con los campos ya calculados que la plantilla necesita.

    `oferta` va tipada como `Oferta` y no como `object`: así pydantic valida de
    verdad y el editor autocompleta los campos dentro de la plantilla.
    """

    oferta: Oferta
    resumen: str | None
    salario: str | None
    motivo: str | None
    notas: list[str]


def _con_extras(evaluacion: Evaluacion, datos: DatosBoletin) -> _Adornada:
    return _Adornada(
        oferta=evaluacion.oferta,
        resumen=datos.resumenes.get(evaluacion.oferta.id),
        salario=_salario(evaluacion),
        motivo=evaluacion.motivo.value if evaluacion.motivo else None,
        notas=evaluacion.notas,
    )


def _salario(evaluacion: Evaluacion) -> str | None:
    o = evaluacion.oferta
    if o.salario_min is None and o.salario_max is None:
        return None
    moneda = o.moneda or ""
    if o.salario_min is not None and o.salario_max is not None:
        return f"{o.salario_min:,} – {o.salario_max:,} {moneda}".replace(",", ".")
    valor = o.salario_min if o.salario_min is not None else o.salario_max
    return f"desde {valor:,} {moneda}".replace(",", ".")


def _agrupar(datos: DatosBoletin) -> list[dict]:
    presencial_co, remoto_co, remoto_global = [], [], []
    for evaluacion in datos.incluidas:
        adornada = _con_extras(evaluacion, datos)
        oferta = evaluacion.oferta
        if oferta.modalidad is not Modalidad.REMOTO:
            presencial_co.append(adornada)
        elif oferta.pais == "CO":
            remoto_co.append(adornada)
        else:
            remoto_global.append(adornada)

    return [
        {"titulo": "Colombia — presencial e híbrido", "ofertas": presencial_co},
        {"titulo": "Colombia — remoto", "ofertas": remoto_co},
        {"titulo": "Remoto internacional", "ofertas": remoto_global},
    ]
