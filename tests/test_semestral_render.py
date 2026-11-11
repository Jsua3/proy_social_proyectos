"""El HTML del boletín: el mismo documento sirve para la web y para el PDF."""

from conftest import leer_datos
from selectolax.parser import HTMLParser

from boletin_semestral.edicion import cargar
from boletin_semestral.modelo import Edicion
from boletin_semestral.render import Modo, copiar_estaticos, manuscrita, parrafos, renderizar


def _edicion_con(carpeta, cambio) -> Edicion:
    datos = leer_datos(carpeta)
    cambio(datos)
    return Edicion.model_validate(datos)


def test_borrador_lleva_marca_y_recuadros(carpeta_edicion):
    def marcar(datos):
        datos["secciones"][1]["pendiente"] = "Falta X"

    html = HTMLParser(renderizar(_edicion_con(carpeta_edicion, marcar), Modo.BORRADOR))

    assert html.css_first(".marca-borrador") is not None
    assert any("Falta X" in p.text() for p in html.css(".pendiente"))


def test_final_no_lleva_marca_ni_recuadros(carpeta_edicion):
    html = HTMLParser(renderizar(cargar(carpeta_edicion), Modo.FINAL))

    assert html.css_first(".marca-borrador") is None
    assert html.css(".pendiente") == []


def test_cada_seccion_es_una_pagina(carpeta_edicion):
    html = HTMLParser(renderizar(cargar(carpeta_edicion), Modo.FINAL))

    assert len(html.css(".pagina.seccion")) == 6
    for clase in ("portada", "editorial", "contraportada"):
        assert html.css_first(f".pagina.{clase}") is not None


def test_titulo_con_manuscrita(carpeta_edicion):
    html = HTMLParser(renderizar(cargar(carpeta_edicion), Modo.FINAL))

    assert "planeta" in [em.text() for em in html.css("em.manuscrita")]


def test_barras_del_comparativo(carpeta_edicion):
    html = renderizar(cargar(carpeta_edicion), Modo.FINAL)

    assert "width: 90.0%" in html
    assert "width: 100.0%" in html
    assert "left: 80.0%" in html
    assert "90,0 %" in html


def test_videos_reproductor_y_qr(carpeta_edicion):
    html = HTMLParser(renderizar(cargar(carpeta_edicion), Modo.FINAL))

    reproductor = html.css_first(".solo-pantalla iframe")
    assert "youtube-nocookie.com/embed/abc123XYZ00" in reproductor.attributes["src"]
    assert html.css_first(".solo-impresion svg") is not None


def test_textos_con_caracteres_especiales(carpeta_edicion):
    def ensuciar(datos):
        datos["secciones"][1]["cuerpo"] = (
            'A & B <script>alert(1)</script> "citas" año ñandú 5 * 3 = 15 * 2'
        )

    html = renderizar(_edicion_con(carpeta_edicion, ensuciar), Modo.FINAL)

    assert "&lt;script&gt;" in html
    assert "<script>alert" not in html
    assert "5 * 3 = 15 * 2" in html
    assert "ñandú" in html
    assert HTMLParser(html).css_first(".seccion--texto .cuerpo em.manuscrita") is None


def test_manuscrita_escapa_y_marca():
    assert str(manuscrita("<b>*hola*</b>")) == '&lt;b&gt;<em class="manuscrita">hola</em>&lt;/b&gt;'


def test_parrafos_y_negrita():
    resultado = str(parrafos("a\n\nb **c**"))

    assert resultado.count("<p>") == 2
    assert "<strong>c</strong>" in resultado


def test_copiar_estaticos(tmp_path):
    copiar_estaticos(tmp_path)

    for nombre in ("estilo.css", "movimiento.js", "logo-humboldt.png"):
        assert (tmp_path / nombre).is_file()
    assert len(list((tmp_path / "fuentes").glob("*.woff2"))) == 5
