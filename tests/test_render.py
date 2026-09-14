from datetime import UTC, date, datetime

from boletin_empleos.modelos import Decision, Evaluacion, Modalidad, MotivoDescarte, Oferta
from boletin_empleos.render.renderizador import DatosBoletin, FuenteUsada, renderizar


def _evaluacion(
    titulo: str,
    modalidad: Modalidad,
    pais: str | None,
    decision=Decision.INCLUIR,
    motivo=None,
    notas=None,
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
