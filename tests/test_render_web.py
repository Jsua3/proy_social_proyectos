"""La edición que se publica en el sitio.

El correo va en MJML porque los clientes de correo son pobres; esta página es web
de verdad y puede usar el lenguaje visual de la universidad sin recortes.
"""

from datetime import UTC, date, datetime

from selectolax.parser import HTMLParser

from boletin_empleos.modelos import Decision, Evaluacion, Modalidad, MotivoDescarte, Oferta
from boletin_empleos.render.renderizador import DatosBoletin, FuenteUsada
from boletin_empleos.render.web import renderizar_web


def _evaluacion(titulo, *, local=False, decision=Decision.INCLUIR, motivo=None, notas=None):
    return Evaluacion(
        oferta=Oferta(
            id=f"x:{titulo}",
            fuente="spe",
            titulo=titulo,
            empresa="Acme S.A.S.",
            ubicacion="Armenia, Quindío" if local else "Bogotá, D.C.",
            pais="CO",
            modalidad=Modalidad.PRESENCIAL,
            url=f"https://ejemplo.co/{titulo}",
            descripcion="Descripción.",
            recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
        ),
        puntaje_relevancia=0.9,
        puntaje_legitimidad=0.9,
        decision=decision,
        motivo=motivo,
        notas=notas or [],
        prioridad_local=local,
    )


def _datos(**extra) -> DatosBoletin:
    base = dict(
        numero_edicion=3,
        fecha=date(2026, 9, 21),
        editorial="Vacantes vigentes recogidas en fuentes verificadas.",
        incluidas=[_evaluacion("Dev Armenia", local=True), _evaluacion("Dev Bogota")],
        conteos={"recibidas": 9722, "incluidas": 2},
        fuentes_usadas=[
            FuenteUsada(
                nombre="spe",
                atribucion="Vacantes del Servicio Público de Empleo.",
                url_atribucion="https://www.serviciodeempleo.gov.co/",
            ),
            FuenteUsada(
                nombre="remoteok",
                atribucion="Ofertas remotas provistas por Remote OK.",
                url_atribucion="https://remoteok.com/",
            ),
        ],
    )
    return DatosBoletin(**(base | extra))


def test_lleva_la_identidad_de_la_universidad():
    html = renderizar_web(_datos())
    arbol = HTMLParser(html)

    imagenes = [i.attributes.get("src", "") for i in arbol.css("img")]
    assert any("logo-humboldt" in src for src in imagenes), "el logo institucional"
    assert "Alexander von Humboldt" in arbol.text()
    assert 'href="../../estilo.css"' in html, "la edición cuelga de <carrera>/ediciones/"


def test_cada_vacante_enlaza_su_oferta_en_una_pestana_nueva():
    html = renderizar_web(_datos())
    arbol = HTMLParser(html)

    ofertas = [a for a in arbol.css("a") if a.attributes.get("href", "").startswith("https://ejem")]
    assert len(ofertas) == 4, "título y 'Ver oferta' por cada una de las dos vacantes"
    for a in ofertas:
        assert a.attributes.get("target") == "_blank"
        assert "noopener" in (a.attributes.get("rel") or "")


def test_el_eje_cafetero_encabeza_y_se_distingue():
    html = renderizar_web(_datos())

    assert "Quindío y eje cafetero" in html
    assert html.index("Quindío y eje cafetero") < html.index("Colombia — presencial")
    assert "seccion--eje" in html, "la sección de la región lleva su propio acento"


def test_muestra_el_embudo_de_la_corrida():
    html = renderizar_web(_datos())
    texto = HTMLParser(html).text()

    assert "9.722" in texto, "las ofertas revisadas, con separador de miles"
    assert "2" in texto


def test_el_apendice_esta_pero_plegado():
    descartada = _evaluacion(
        "Estafa",
        decision=Decision.DESCARTAR,
        motivo=MotivoDescarte.LEGITIMIDAD,
        notas=["pide dinero al aspirante"],
    )
    html = renderizar_web(_datos(descartadas=[descartada]))
    arbol = HTMLParser(html)

    detalles = arbol.css("details")
    assert detalles, "el apéndice no debe ocupar la pantalla, pero tiene que estar"
    assert detalles[0].attributes.get("open") is None
    assert "pide dinero al aspirante" in arbol.text()


def test_cita_todas_las_fuentes_y_declara_las_caidas():
    html = renderizar_web(_datos(fuentes_caidas=["magneto"]))
    texto = HTMLParser(html).text()

    assert "Servicio Público de Empleo" in texto
    assert "Remote OK" in texto
    assert "magneto" in texto and "no respondió" in texto


def test_escapa_el_contenido_de_terceros():
    peligrosa = _evaluacion("<script>alert(1)</script>")
    html = renderizar_web(_datos(incluidas=[peligrosa]))

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_vuelve_al_indice_del_sitio():
    html = renderizar_web(_datos())
    arbol = HTMLParser(html)

    assert [a for a in arbol.css("a") if a.attributes.get("href") == "../index.html"]


def test_la_pagina_dice_de_que_carrera_es():
    html = renderizar_web(_datos(programa="Ingeniería Industrial"))
    texto = HTMLParser(html).text()

    assert "Ingeniería Industrial" in texto
    assert "Ingeniería de Software" not in texto
