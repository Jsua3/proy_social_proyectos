"""El núcleo no puede hacer E/S. Es la invariante que lo mantiene testeable."""

from pathlib import Path

PROHIBIDOS = ("httpx", "requests", "smtplib", "urllib", "socket", "sqlite3", "open(")
NUCLEO = Path(__file__).resolve().parents[1] / "src" / "boletin_empleos" / "nucleo"


def test_el_nucleo_no_importa_nada_de_entrada_salida():
    infracciones = []
    for archivo in NUCLEO.glob("*.py"):
        texto = archivo.read_text("utf-8")
        for prohibido in PROHIBIDOS:
            if prohibido in texto:
                infracciones.append(f"{archivo.name}: {prohibido}")
    assert not infracciones, f"el núcleo debe ser puro, pero encontré: {infracciones}"
