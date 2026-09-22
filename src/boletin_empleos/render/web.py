"""La edición como página web, con la identidad de la universidad.

El correo va en MJML porque los clientes de correo apenas entienden CSS de 2005.
Esta página no tiene esa limitación: usa los colores del escudo (#143D68 y
#BD1822), materiales translúcidos con profundidad y respuesta inmediata al
presionar, siguiendo el lenguaje de iOS 26.

Todo lo que venga de terceros —títulos, empresas, resúmenes— se escapa: son
datos de portales externos y de un modelo de lenguaje.
"""

from html import escape
from pathlib import Path

from boletin_empleos.render.formato import en_palabras, miles
from boletin_empleos.render.renderizador import (
    MOTIVOS_DETALLE,
    DatosBoletin,
    agregar_descartes,
    agrupar,
    con_extras,
)

ESTATICOS = Path(__file__).parent / "estaticos"

# Lo que hay que copiar al sitio para que las páginas se vean como deben.
ARCHIVOS_ESTATICOS = ("estilo.css", "logo-humboldt.png", "movimiento.js")

INSTITUCION = "Corporación Universitaria Empresarial Alexander von Humboldt"
UNIDAD = "Proyección Social · Facultad de Ingenierías y Ciencias Básicas"


def pagina(
    *,
    titulo: str,
    descripcion: str,
    cuerpo: str,
    profundidad: str = "",
    accion: str = "",
    subtitulo: str = UNIDAD,
) -> str:
    """El armazón común del sitio: barra flotante con el escudo y contenido debajo."""
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#143D68">
<title>{escape(titulo)}</title>
<meta name="description" content="{escape(descripcion)}">
<link rel="icon" href="{profundidad}logo-humboldt.png">
<link rel="stylesheet" href="{profundidad}estilo.css">
</head>
<body>
<header class="barra">
  <div class="barra__interior">
    <span class="marca"><img src="{profundidad}logo-humboldt.png"
      alt="{escape(INSTITUCION)}"></span>
    <span class="barra__texto">
      <span class="barra__titulo">Boletín de empleos</span>
      <span class="barra__pie">{escape(subtitulo)}</span>
    </span>
    {accion}
  </div>
</header>
<main class="envoltura">
{cuerpo}
</main>
<script src="{profundidad}movimiento.js" defer></script>
</body>
</html>
"""


def renderizar_web(datos: DatosBoletin) -> str:
    """La edición completa: la que se archiva y la que enlaza el correo."""
    total = len(datos.incluidas)
    del_eje = sum(1 for e in datos.incluidas if e.prioridad_local)

    con_vacantes = [s for s in agrupar(datos) if s["ofertas"]]
    cuerpo = "\n".join(
        [
            _portada(datos, total, del_eje),
            _filtro(con_vacantes, total),
            _secciones(datos),
            _apendice(datos),
            _pie(datos),
        ]
    )
    return pagina(
        titulo=f"Boletín de empleos — {datos.programa} · {en_palabras(datos.fecha)}",
        subtitulo=f"{datos.programa} · Proyección Social" if datos.programa else UNIDAD,
        descripcion=(
            f"{total} vacantes vigentes, filtradas por pertinencia para los egresados "
            f"de {datos.programa}."
        ),
        cuerpo=cuerpo,
        profundidad="../../",
        accion='<a class="boton boton--tenue barra__accion" href="../index.html">Ediciones</a>',
    )


def _portada(datos: DatosBoletin, total: int, del_eje: int) -> str:
    cifras = [
        (miles(datos.conteos.get("recibidas", 0)), "ofertas revisadas"),
        (miles(total), "vacantes publicadas"),
        (miles(del_eje), "del eje cafetero"),
        (miles(len(datos.fuentes_usadas)), "portales consultados"),
    ]
    tarjetas = "\n".join(
        f'      <li class="cifra"><div class="cifra__valor">{valor}</div>'
        f'<div class="cifra__nombre">{nombre}</div></li>'
        for valor, nombre in cifras
    )
    plural = "vacante" if total == 1 else "vacantes"
    return f"""  <section class="portada aparece">
    <span class="etiqueta">Edición {datos.numero_edicion} · {en_palabras(datos.fecha)}</span>
    <h1>{miles(total)} {plural} para nuestros egresados</h1>
    <p>{escape(datos.editorial)}</p>
    <ul class="cifras">
{tarjetas}
    </ul>
  </section>"""


def _filtro(secciones: list[dict], total: int) -> str:
    """Atajo a la parte de la edición que le interesa a quien lee.

    Una edición puede traer cientos de vacantes y la mayoría presenciales en otra
    ciudad. Quien sí quiere mirar fuera del eje —o fuera del país— no tiene por
    qué recorrer la página entera. Con una sola sección no se dibuja: sería un
    control que no controla nada.
    """
    if len(secciones) < 2:
        return ""

    pastillas = [
        '      <button class="filtro__pastilla filtro__pastilla--activa" type="button"'
        ' data-filtro="todas" aria-pressed="true">Todas'
        f' <span class="filtro__cuenta">{miles(total)}</span></button>'
    ]
    pastillas += [
        f'      <button class="filtro__pastilla" type="button" data-filtro="{s["clave"]}"'
        f' aria-pressed="false">{escape(s["titulo"])}'
        f' <span class="filtro__cuenta">{miles(len(s["ofertas"]))}</span></button>'
        for s in secciones
    ]
    botones = "\n".join(pastillas)
    return f"""  <nav class="filtro aparece" aria-label="Filtrar las vacantes por lugar">
{botones}
  </nav>"""


def _secciones(datos: DatosBoletin) -> str:
    partes = []
    for seccion in agrupar(datos):
        if not seccion["ofertas"]:
            continue
        clase = "seccion seccion--eje" if seccion["clave"] == "eje" else "seccion"
        tarjetas = "\n".join(_vacante(a) for a in seccion["ofertas"])
        partes.append(
            f"""  <section class="{clase} aparece" id="{seccion["clave"]}" \
data-seccion="{seccion["clave"]}">
    <h2 class="seccion__titulo">{escape(seccion["titulo"])}
      <span class="seccion__cuenta">{len(seccion["ofertas"])}</span>
    </h2>
    <ul class="vacantes">
{tarjetas}
    </ul>
  </section>"""
        )
    return "\n".join(partes)


def _vacante(adornada) -> str:
    oferta = adornada.oferta
    url = escape(str(oferta.url), quote=True)
    meta = " · ".join(
        escape(str(parte))
        for parte in (
            oferta.empresa or "Empresa no identificada",
            oferta.ubicacion,
            f"publicada {oferta.fecha_publicacion}" if oferta.fecha_publicacion else None,
        )
        if parte
    )
    resumen = (
        f'\n      <p class="vacante__resumen">{escape(adornada.resumen)}</p>'
        if adornada.resumen
        else ""
    )
    salario = (
        f'\n        <span class="salario">{escape(adornada.salario)}</span>'
        if adornada.salario
        else ""
    )
    return f"""      <li class="vacante">
      <h3 class="vacante__titulo"><a href="{url}" target="_blank" rel="noopener noreferrer">{
        escape(oferta.titulo)
    }</a></h3>
      <p class="vacante__meta">{meta}</p>{resumen}
      <div class="vacante__pie">
        <a class="boton" href="{url}" target="_blank" rel="noopener noreferrer">Ver oferta</a>{
        salario
    }
      </div>
    </li>"""


def _apendice(datos: DatosBoletin) -> str:
    detalle = [con_extras(e, datos) for e in datos.descartadas if e.motivo in MOTIVOS_DETALLE]
    agregados = agregar_descartes(datos.descartadas)
    if not detalle and not agregados:
        return ""

    lineas = [
        f"      <p><strong>{escape(a.oferta.titulo)}</strong> — {escape(a.motivo or '')}: "
        f"{escape('; '.join(a.notas))}</p>"
        for a in detalle
    ]
    lineas += [
        f"      <p>{a['conteo']} descartadas por {escape(a['etiqueta'])}.</p>" for a in agregados
    ]
    cuerpo = "\n".join(lineas)
    return f"""  <details class="apendice aparece">
    <summary>Qué se descartó y por qué</summary>
    <div class="apendice__cuerpo">
      <p>Se listan para que el filtro pueda auditarse. Nada se descarta en silencio.</p>
{cuerpo}
    </div>
  </details>"""


def _pie(datos: DatosBoletin) -> str:
    fuentes = "\n".join(
        f"      <li>{escape(f.atribucion)} "
        f'<a href="{escape(f.url_atribucion, quote=True)}" target="_blank" '
        f'rel="noopener noreferrer">{escape(f.url_atribucion)}</a></li>'
        for f in datos.fuentes_usadas
    )
    caidas = (
        f'\n    <p class="aviso">En esta edición no respondió: '
        f"{escape(', '.join(datos.fuentes_caidas))}.</p>"
        if datos.fuentes_caidas
        else ""
    )
    return f"""  <footer class="pie aparece">
    <p><strong>{escape(UNIDAD)}</strong><br>{escape(INSTITUCION)} · Armenia, Quindío</p>
    <p>Vacantes recogidas en fuentes que autorizan expresamente su uso:</p>
    <ul class="pie__fuentes">
{fuentes}
    </ul>{caidas}
  </footer>"""
