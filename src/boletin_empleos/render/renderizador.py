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
from boletin_empleos.render.formato import en_palabras

_PLANTILLAS = Path(__file__).parent / "plantillas"

# Qué llega al apéndice del boletín y cómo (spec §8.6):
#  - Legitimidad: con la señal que lo activó -> detalle por ítem.
#  - Experiencia, vigencia y enlace muerto: en conteo agregado -> nunca el
#    título ni las notas de la oferta, para no inundar el apéndice.
#  - Relevancia y deduplicación: no llegan al apéndice (quedan en el registro).
MOTIVOS_DETALLE = {MotivoDescarte.LEGITIMIDAD}

_ETIQUETAS_AGREGADAS = {
    MotivoDescarte.EXPERIENCIA: "nivel de experiencia",
    MotivoDescarte.VIGENCIA: "vigencia",
    MotivoDescarte.ENLACE_MUERTO: "enlace muerto",
}


class FuenteUsada(BaseModel):
    nombre: str
    atribucion: str
    url_atribucion: str


class DatosBoletin(BaseModel):
    # "Ingeniería de Software", "Ingeniería Industrial": el mismo código sirve a
    # todas las carreras y cada edición dice de cuál es.
    programa: str = ""
    numero_edicion: int
    fecha: date
    editorial: str
    incluidas: list[Evaluacion]
    descartadas: list[Evaluacion] = Field(default_factory=list)
    resumenes: dict[str, str] = Field(default_factory=dict)
    conteos: dict[str, int] = Field(default_factory=dict)
    fuentes_usadas: list[FuenteUsada] = Field(default_factory=list)
    fuentes_caidas: list[str] = Field(default_factory=list)
    # Versión para correo: el boletín completo ronda los 300 KB y Gmail recorta
    # los mensajes de más de unos 102 KB. Con `url_edicion` el render deja de
    # incluir el apéndice y añade el enlace a la edición publicada en la web;
    # con `tope_vacantes` solo muestra las primeras, que el pipeline ya ordenó
    # de más a menos pertinente.
    url_edicion: str | None = None
    tope_vacantes: int | None = None
    # El escudo se sirve desde el sitio: en un correo no se puede adjuntar
    # sin engordarlo, y sin sitio publicado no hay dónde servirlo.
    url_logo: str | None = None


def renderizar(datos: DatosBoletin) -> str:
    # autoescape=True: los títulos, empresas, resúmenes y editorial pueden venir
    # de terceros (fuentes externas) o de un LLM. Sin escapar, un '<'/'>' rompe
    # el XML que MJML necesita parsear y aborta TODO el boletín; un '&' sin
    # escapar deja el HTML final inválido. Esto también evita inyección de HTML
    # en el correo institucional.
    entorno = Environment(loader=_cargador(), autoescape=True)
    plantilla = entorno.get_template("boletin.mjml")
    # En el correo el apéndice sobra: es lo que más pesa y la edición completa
    # queda a un clic.
    es_correo = datos.url_edicion is not None
    return plantilla.render(
        programa=datos.programa,
        numero_edicion=datos.numero_edicion,
        fecha=en_palabras(datos.fecha),
        editorial=datos.editorial,
        conteos=datos.conteos,
        secciones=agrupar(datos),
        descartes_detalle=[]
        if es_correo
        else [con_extras(e, datos) for e in datos.descartadas if e.motivo in MOTIVOS_DETALLE],
        descartes_agregados=[] if es_correo else agregar_descartes(datos.descartadas),
        fuentes_usadas=datos.fuentes_usadas,
        fuentes_caidas=datos.fuentes_caidas,
        url_edicion=datos.url_edicion,
        url_logo=datos.url_logo,
        total_vacantes=len(datos.incluidas),
    )


def agregar_descartes(descartadas: list[Evaluacion]) -> list[dict]:
    """Conteo agregado por motivo (spec §8.6): nunca título ni notas por ítem."""
    conteos_por_motivo: dict[MotivoDescarte, int] = {}
    for evaluacion in descartadas:
        if evaluacion.motivo in _ETIQUETAS_AGREGADAS:
            conteos_por_motivo[evaluacion.motivo] = conteos_por_motivo.get(evaluacion.motivo, 0) + 1

    return [
        {"etiqueta": _ETIQUETAS_AGREGADAS[motivo], "conteo": conteos_por_motivo[motivo]}
        for motivo in _ETIQUETAS_AGREGADAS
        if motivo in conteos_por_motivo
    ]


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


def con_extras(evaluacion: Evaluacion, datos: DatosBoletin) -> _Adornada:
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


def agrupar(datos: DatosBoletin) -> list[dict]:
    """Ordena por cercanía a Armenia: primero la región, después lo alcanzable.

    Una vacante remota en Colombia se puede tomar desde Armenia; una presencial
    en Medellín exige mudarse. Por eso el remoto nacional va antes. Cada vacante
    cae en la primera sección que le corresponde, nunca en dos.
    """
    eje, presencial_co, remoto_co, remoto_global = [], [], [], []
    mostradas = datos.incluidas[: datos.tope_vacantes] if datos.tope_vacantes else datos.incluidas
    for evaluacion in mostradas:
        adornada = con_extras(evaluacion, datos)
        oferta = evaluacion.oferta
        if evaluacion.prioridad_local:
            eje.append(adornada)
        elif oferta.modalidad is not Modalidad.REMOTO:
            presencial_co.append(adornada)
        elif oferta.pais == "CO":
            remoto_co.append(adornada)
        else:
            remoto_global.append(adornada)

    # La clave identifica la sección para el filtro de la página y para el ancla
    # de la URL; el título es lo que lee la gente.
    return [
        {"clave": "eje", "titulo": "Quindío y eje cafetero", "ofertas": eje},
        {"clave": "remoto-co", "titulo": "Colombia — remoto", "ofertas": remoto_co},
        {
            "clave": "presencial-co",
            "titulo": "Colombia — presencial e híbrido",
            "ofertas": presencial_co,
        },
        {"clave": "internacional", "titulo": "Remoto internacional", "ofertas": remoto_global},
    ]
