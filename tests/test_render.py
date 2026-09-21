from datetime import UTC, date, datetime

from selectolax.parser import HTMLParser

from boletin_empleos.modelos import Decision, Evaluacion, Modalidad, MotivoDescarte, Oferta
from boletin_empleos.render.renderizador import DatosBoletin, FuenteUsada, renderizar


def _evaluacion(
    titulo: str,
    modalidad: Modalidad,
    pais: str | None,
    decision=Decision.INCLUIR,
    motivo=None,
    notas=None,
    prioridad_local: bool = False,
) -> Evaluacion:
    return Evaluacion(
        oferta=Oferta(
            id=f"x:{titulo}",
            fuente="spe",
            titulo=titulo,
            empresa="Acme S.A.S.",
            ubicacion="Armenia, Quindío",
            pais=pais,
            modalidad=modalidad,
            url="https://ejemplo.co/1",
            descripcion="Descripción.",
            recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
        ),
        puntaje_relevancia=0.9,
        puntaje_legitimidad=0.9,
        decision=decision,
        motivo=motivo,
        notas=notas or [],
        prioridad_local=prioridad_local,
    )


def _datos(**extra) -> DatosBoletin:
    base = dict(
        numero_edicion=8,
        fecha=date(2026, 9, 22),
        editorial="Texto editorial de la edición.",
        incluidas=[
            _evaluacion("Dev Presencial", Modalidad.PRESENCIAL, "CO"),
            _evaluacion("Dev Remoto CO", Modalidad.REMOTO, "CO"),
            _evaluacion("Dev Remoto Global", Modalidad.REMOTO, None),
        ],
        descartadas=[],
        resumenes={},
        conteos={"recibidas": 100, "incluidas": 3},
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
        fuentes_caidas=[],
    )
    return DatosBoletin(**(base | extra))


def test_el_html_incluye_titulos_y_enlaces():
    html = renderizar(_datos())
    assert "Dev Presencial" in html
    assert "https://ejemplo.co/1" in html
    assert "<html" in html.lower()


def test_agrupa_en_las_tres_secciones():
    html = renderizar(_datos())
    assert "Colombia — presencial" in html
    assert "Colombia — remoto" in html
    assert "Remoto internacional" in html


def test_el_pie_cita_todas_las_fuentes_usadas():
    """Remotive y RemoteOK cortan el acceso si no se les cita."""
    html = renderizar(_datos())
    assert "Servicio Público de Empleo" in html
    assert "Remote OK" in html
    assert "https://remoteok.com/" in html


def test_declara_las_fuentes_caidas():
    html = renderizar(_datos(fuentes_caidas=["magneto"]))
    assert "magneto" in html
    assert "no respondió" in html


def test_el_apendice_muestra_solo_los_descartes_pertinentes():
    descartadas = [
        _evaluacion(
            "Estafa",
            Modalidad.REMOTO,
            "CO",
            Decision.DESCARTAR,
            MotivoDescarte.LEGITIMIDAD,
            ["pide dinero al aspirante"],
        ),
        _evaluacion(
            "Contadora",
            Modalidad.REMOTO,
            "CO",
            Decision.DESCARTAR,
            MotivoDescarte.RELEVANCIA,
            ["relevancia 0.10"],
        ),
    ]
    html = renderizar(_datos(descartadas=descartadas))
    assert "pide dinero al aspirante" in html
    assert "Contadora" not in html, "los descartes por relevancia no van al apéndice (spec §8.6)"


def test_escapa_html_en_titulo_y_resumen_sin_romper_el_render():
    """F1: '<', '>' o '&' en datos de terceros (o generados por IA) no debe romper
    renderizar() ni inyectar HTML crudo en el correo institucional."""
    ev = _evaluacion("R&D <Senior> Dev", Modalidad.PRESENCIAL, "CO")
    resumen_malicioso = "<script>alert(1)</script>"

    html = renderizar(_datos(incluidas=[ev], resumenes={ev.oferta.id: resumen_malicioso}))

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "R&amp;D &lt;Senior&gt; Dev" in html


def test_el_apendice_agrega_experiencia_vigencia_y_enlace_muerto():
    """F3: el apéndice sigue la tabla del spec §8.6 — legitimidad se detalla con
    la señal que lo activó; experiencia, vigencia y enlace muerto van en conteo
    agregado, nunca con el título ni las notas de cada oferta."""
    descartadas = [
        _evaluacion(
            "Estafa",
            Modalidad.REMOTO,
            "CO",
            Decision.DESCARTAR,
            MotivoDescarte.LEGITIMIDAD,
            ["pide dinero al aspirante"],
        ),
        _evaluacion(
            "Senior Dev A",
            Modalidad.REMOTO,
            "CO",
            Decision.DESCARTAR,
            MotivoDescarte.EXPERIENCIA,
            ["el título indica un nivel de experiencia alto: 'senior'"],
        ),
        _evaluacion(
            "Senior Dev B",
            Modalidad.REMOTO,
            "CO",
            Decision.DESCARTAR,
            MotivoDescarte.EXPERIENCIA,
            ["el título indica un nivel de experiencia alto: 'senior'"],
        ),
        _evaluacion(
            "Oferta vencida",
            Modalidad.REMOTO,
            "CO",
            Decision.DESCARTAR,
            MotivoDescarte.VIGENCIA,
            ["publicada hace más de 30 días"],
        ),
        _evaluacion(
            "Enlace roto",
            Modalidad.REMOTO,
            "CO",
            Decision.DESCARTAR,
            MotivoDescarte.ENLACE_MUERTO,
            ["el enlace ya no responde"],
        ),
    ]

    html = renderizar(_datos(descartadas=descartadas))

    # Legitimidad: detalle por ítem, con la señal que lo activó.
    assert "Estafa" in html
    assert "pide dinero al aspirante" in html

    # Experiencia, vigencia y enlace muerto: solo conteo agregado, nunca el
    # título individual ni las notas de cada oferta.
    assert "Senior Dev A" not in html
    assert "Senior Dev B" not in html
    assert "Oferta vencida" not in html
    assert "Enlace roto" not in html
    assert "el enlace ya no responde" not in html
    assert "2 descartadas por nivel de experiencia." in html
    assert "1 descartadas por vigencia." in html
    assert "1 descartadas por enlace muerto." in html


def test_usa_el_resumen_cuando_existe():
    ev = _evaluacion("Dev Presencial", Modalidad.PRESENCIAL, "CO")
    html = renderizar(_datos(incluidas=[ev], resumenes={ev.oferta.id: "Construye APIs en Python."}))
    assert "Construye APIs en Python." in html


def test_boletin_sin_ofertas_sigue_siendo_html_valido():
    html = renderizar(_datos(incluidas=[]))
    assert "<html" in html.lower()


# --- Ronda 2 — R2-7: enlaces visibles y abribles a cada oferta ---------------


def _evaluacion_con_url(titulo: str, url: str) -> Evaluacion:
    return Evaluacion(
        oferta=Oferta(
            id=f"x:{titulo}",
            fuente="spe",
            titulo=titulo,
            modalidad=Modalidad.PRESENCIAL,
            url=url,
            descripcion="Descripción.",
            recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
        ),
        puntaje_relevancia=0.9,
        puntaje_legitimidad=0.9,
        decision=Decision.INCLUIR,
    )


def test_r2_7_cada_oferta_tiene_exactamente_un_ver_oferta_a_su_propia_url():
    ev1 = _evaluacion_con_url("Dev Uno", "https://ejemplo.co/1")
    ev2 = _evaluacion_con_url("Dev Dos", "https://ejemplo.co/2")
    html = renderizar(_datos(incluidas=[ev1, ev2]))
    arbol = HTMLParser(html)

    enlaces_ver_oferta = [a for a in arbol.css("a") if a.text(strip=True).startswith("Ver oferta")]
    assert len(enlaces_ver_oferta) == 2, "un 'Ver oferta' por cada una de las dos ofertas"
    hrefs = {a.attributes.get("href") for a in enlaces_ver_oferta}
    assert hrefs == {"https://ejemplo.co/1", "https://ejemplo.co/2"}


def test_r2_7_todos_los_enlaces_abren_en_pestana_nueva_sin_opener():
    html = renderizar(_datos())
    arbol = HTMLParser(html)
    enlaces = arbol.css("a")
    assert enlaces, "debe haber al menos un enlace en el boletín"
    for a in enlaces:
        assert a.attributes.get("target") == "_blank", a.html
        assert "noopener" in (a.attributes.get("rel") or ""), a.html


def test_r2_7_la_url_del_spe_con_ampersand_en_la_query_sobrevive_intacta():
    """Con el autoescape de la ronda 1, el `&` debe quedar como `&amp;` en el

    atributo, pero seguir llevando exactamente a la misma URL."""
    url_spe = (
        "https://personas.serviciodeempleo.gov.co/detalle_oferta.aspx"
        "?sede_id=1626535798&proceso_id=2&dep_id=63"
    )
    ev = _evaluacion_con_url("Dev SPE", url_spe)
    html = renderizar(_datos(incluidas=[ev]))

    assert "&amp;" in html, "el '&' de la query debe seguir escapado en el atributo"
    arbol = HTMLParser(html)
    enlace_titulo = arbol.css_first('a[href*="detalle_oferta.aspx"]')
    assert enlace_titulo.attributes.get("href") == url_spe


# --- Correo corto con enlace a la edición completa -------------------------------
# El boletín completo pesa unos 300 KB y Gmail recorta los correos de más de unos
# 102 KB. El correo lleva las vacantes más pertinentes y enlaza a la edición
# publicada en la web; el archivo completo se conserva allá.

URL_EDICION = "https://jsua3.github.io/proy_social_proyectos/ediciones/2026-09-22.html"


def test_el_correo_corto_muestra_solo_el_tope_de_vacantes():
    html = renderizar(_datos(tope_vacantes=2, url_edicion=URL_EDICION))
    arbol = HTMLParser(html)
    assert len([a for a in arbol.css("a") if a.text(strip=True).startswith("Ver oferta")]) == 2


def test_el_correo_corto_enlaza_la_edicion_completa_y_dice_cuantas_hay():
    html = renderizar(_datos(tope_vacantes=2, url_edicion=URL_EDICION))
    arbol = HTMLParser(html)

    enlace = next(a for a in arbol.css("a") if a.attributes.get("href") == URL_EDICION)
    assert "3" in enlace.text(), "el enlace dice cuántas vacantes trae la edición completa"


def test_el_correo_corto_no_lleva_el_apendice():
    """El apéndice es lo que más pesa; en la web sí va completo."""
    descartadas = [
        _evaluacion(
            "Estafa",
            Modalidad.REMOTO,
            "CO",
            Decision.DESCARTAR,
            MotivoDescarte.LEGITIMIDAD,
            ["pide dinero al aspirante"],
        )
    ]
    html = renderizar(_datos(tope_vacantes=2, url_edicion=URL_EDICION, descartadas=descartadas))

    assert "Apéndice" not in html
    assert "pide dinero al aspirante" not in html


def test_el_correo_corto_conserva_las_atribuciones():
    """Remotive y RemoteOK exigen la cita en lo que se distribuye, no solo en la web."""
    html = renderizar(_datos(tope_vacantes=1, url_edicion=URL_EDICION))

    assert "Servicio Público de Empleo" in html
    assert "Remote OK" in html


def test_el_enlace_a_la_edicion_tambien_abre_en_pestana_nueva():
    html = renderizar(_datos(tope_vacantes=1, url_edicion=URL_EDICION))
    arbol = HTMLParser(html)

    hacia_la_edicion = next(a for a in arbol.css("a") if a.attributes.get("href") == URL_EDICION)
    assert hacia_la_edicion.attributes.get("target") == "_blank"
    assert "noopener" in (hacia_la_edicion.attributes.get("rel") or "")


def test_sin_tope_el_boletin_lleva_todas_las_vacantes_y_su_apendice():
    """La edición de la web no cambia: es la que se archiva y la que enlaza el correo."""
    descartadas = [
        _evaluacion(
            "Estafa",
            Modalidad.REMOTO,
            "CO",
            Decision.DESCARTAR,
            MotivoDescarte.LEGITIMIDAD,
            ["pide dinero al aspirante"],
        )
    ]
    html = renderizar(_datos(descartadas=descartadas))
    arbol = HTMLParser(html)

    assert len([a for a in arbol.css("a") if a.text(strip=True).startswith("Ver oferta")]) == 3
    assert "pide dinero al aspirante" in html


# --- Prioridad del eje cafetero -------------------------------------------------


def test_las_vacantes_del_eje_cafetero_encabezan_el_boletin():
    cerca = _evaluacion("Dev Armenia", Modalidad.PRESENCIAL, "CO", prioridad_local=True)
    html = renderizar(_datos(incluidas=[*_datos().incluidas, cerca]))

    assert "Quindío y eje cafetero" in html
    assert html.index("Quindío y eje cafetero") < html.index("Colombia — remoto")
    assert html.index("Quindío y eje cafetero") < html.index("Colombia — presencial")


def test_una_vacante_del_eje_aparece_una_sola_vez():
    """Aunque sea remota y colombiana, no puede salir en dos secciones."""
    cerca = _evaluacion("Dev Pereira remoto", Modalidad.REMOTO, "CO", prioridad_local=True)
    html = renderizar(_datos(incluidas=[cerca]))

    assert html.count("Dev Pereira remoto") == 1


def test_el_remoto_nacional_va_antes_que_lo_presencial_de_otra_ciudad():
    """Desde Armenia, una vacante remota es más alcanzable que una en Medellín."""
    html = renderizar(_datos())

    assert html.index("Colombia — remoto") < html.index("Colombia — presencial")


def test_el_correo_lleva_el_escudo_cuando_hay_sitio_donde_servirlo():
    html = renderizar(_datos(url_logo="https://ejemplo.github.io/repo/logo-humboldt.png"))
    arbol = HTMLParser(html)

    fuentes = [i.attributes.get("src", "") for i in arbol.css("img")]
    assert any("logo-humboldt" in src for src in fuentes)
    assert "Alexander von Humboldt" in html


def test_sin_sitio_el_correo_no_deja_una_imagen_rota():
    html = renderizar(_datos())
    arbol = HTMLParser(html)

    assert not [i for i in arbol.css("img") if "logo" in i.attributes.get("src", "")]
    assert "Alexander von Humboldt" in html, "el nombre de la institución va siempre"
