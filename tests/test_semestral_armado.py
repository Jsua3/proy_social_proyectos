"""`armar` deja la vista previa o la edición publicada; la consola dice qué falta."""

import io
import sys
from pathlib import Path

import pytest
from conftest import foto_jpg

from boletin_semestral import armado
from boletin_semestral.armado import armar
from boletin_semestral.cli import main
from boletin_semestral.edicion import ErrorEdicion
from boletin_semestral.pdf import ChromiumAusente, ResultadoPdf


def generar_falso(html: Path, destino: Path) -> ResultadoPdf:
    Path(destino).write_bytes(b"%PDF-falso")
    return ResultadoPdf(paginas=9, largas=[])


def _reescribir(carpeta, viejo: str, nuevo: str) -> None:
    archivo = carpeta / "edicion.toml"
    texto = archivo.read_text(encoding="utf-8")
    assert viejo in texto
    archivo.write_text(texto.replace(viejo, nuevo), encoding="utf-8")


def _aprobar(carpeta) -> None:
    _reescribir(carpeta, 'estado = "borrador"', 'estado = "aprobada"')


def _marcar_pendiente(carpeta) -> None:
    _reescribir(
        carpeta,
        'cuerpo = "VII jornada de siembra."',
        'cuerpo = "VII jornada de siembra."\npendiente = "Faltan fotos de la siembra"',
    )


def test_borrador_va_a_salida_con_marca(carpeta_edicion, tmp_path):
    resultado = armar(carpeta_edicion, tmp_path / "salida", generar=generar_falso)

    destino = tmp_path / "salida" / "2026-2"
    assert resultado.publicada is False
    assert resultado.destino == destino
    assert "marca-borrador" in (destino / "index.html").read_text(encoding="utf-8")
    assert resultado.pdf == destino / "boletin-vol-8-borrador.pdf"
    assert resultado.pdf.is_file()
    assert not (carpeta_edicion / "publicada").exists()


def test_aprobada_con_pendientes_no_se_publica(carpeta_edicion, tmp_path):
    _aprobar(carpeta_edicion)
    _marcar_pendiente(carpeta_edicion)

    with pytest.raises(ErrorEdicion, match="Planeta"):
        armar(carpeta_edicion, tmp_path / "salida", generar=generar_falso)

    assert not (carpeta_edicion / "publicada").exists()


def test_aprobada_sin_pendientes_genera_publicada(carpeta_edicion, tmp_path):
    _aprobar(carpeta_edicion)

    resultado = armar(carpeta_edicion, tmp_path / "salida", generar=generar_falso)

    publicada = carpeta_edicion / "publicada"
    assert resultado.publicada is True
    assert "marca-borrador" not in (publicada / "index.html").read_text(encoding="utf-8")
    assert (publicada / "boletin-vol-8.pdf").is_file()
    assert (publicada / "fotos" / "siembra.jpg").is_file()
    assert (publicada / "estilo.css").is_file()


def test_publicada_se_regenera_desde_cero(carpeta_edicion, tmp_path):
    _aprobar(carpeta_edicion)
    armar(carpeta_edicion, tmp_path / "salida", generar=generar_falso)
    assert (carpeta_edicion / "publicada" / "fotos" / "taller.jpg").is_file()

    _reescribir(carpeta_edicion, ', { archivo = "taller.jpg", pie = "Taller" }', "")
    _reescribir(carpeta_edicion, 'foto = "taller.jpg"', "")
    armar(carpeta_edicion, tmp_path / "salida", generar=generar_falso)

    assert not (carpeta_edicion / "publicada" / "fotos" / "taller.jpg").exists()


def test_solo_se_copian_las_fotos_nombradas(carpeta_edicion, tmp_path):
    foto_jpg(carpeta_edicion / "fotos" / "extra.jpg")

    armar(carpeta_edicion, tmp_path / "salida", generar=generar_falso)

    assert not (tmp_path / "salida" / "2026-2" / "fotos" / "extra.jpg").exists()


def _argumentos(carpeta_edicion, tmp_path) -> list[str]:
    return ["armar", "2026-2", "--datos", str(carpeta_edicion.parent), "--salida", str(tmp_path)]


def test_cli_armar_imprime_pendientes(capsys, monkeypatch, carpeta_edicion, tmp_path):
    monkeypatch.setattr(armado, "generar_pdf", generar_falso)
    _marcar_pendiente(carpeta_edicion)

    codigo = main(_argumentos(carpeta_edicion, tmp_path / "salida"))

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "Pendientes (1):" in salida
    assert "Faltan fotos de la siembra" in salida


def test_cli_error_de_archivo_devuelve_1(capsys, carpeta_edicion, tmp_path):
    _reescribir(carpeta_edicion, 'fecha = "Diciembre 2026"', 'fecha = "sin cerrar')

    codigo = main(_argumentos(carpeta_edicion, tmp_path / "salida"))

    assert codigo == 1
    assert "línea" in capsys.readouterr().err


def test_cli_sin_chromium_devuelve_1(capsys, monkeypatch, carpeta_edicion, tmp_path):
    def sin_chromium(html, destino):
        raise ChromiumAusente("Instálalo con: uv run playwright install chromium")

    monkeypatch.setattr(armado, "generar_pdf", sin_chromium)

    codigo = main(_argumentos(carpeta_edicion, tmp_path / "salida"))

    assert codigo == 1
    assert "playwright install chromium" in capsys.readouterr().err


def test_cli_escribe_en_utf8(monkeypatch, tmp_path):
    # En Windows, si la salida va por una tubería (Git Bash), Python escribe en cp1252
    # y las tildes llegan rotas. La consola siempre debe escribir UTF-8.
    crudo = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(crudo, encoding="cp1252"))

    main(["nueva", "2026-2", "--datos", str(tmp_path / "semestral")])
    sys.stdout.flush()

    assert "Edición creada".encode() in crudo.getvalue()


def test_cli_nueva(capsys, tmp_path):
    base = tmp_path / "semestral"

    codigo = main(["nueva", "2026-2", "--datos", str(base)])

    assert codigo == 0
    assert (base / "2026-2" / "edicion.toml").is_file()
    assert "2026-2" in capsys.readouterr().out
