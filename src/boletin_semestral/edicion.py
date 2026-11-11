"""Leer `edicion.toml` con mensajes que un monitor entienda, y crear la edición siguiente."""

import re
import tomllib
from pathlib import Path

import tomli_w
from pydantic import ValidationError

from boletin_semestral.modelo import TIPOS_DE_SECCION, Edicion, fotos_nombradas

ARCHIVO = "edicion.toml"
ESQUELETO = Path(__file__).parent / "esqueleto.toml"
_SEMESTRE = re.compile(r"^(\d{4})-([12])$")
_SECCIONES_GENERALES = ("portada", "editorial", "contraportada")


class ErrorEdicion(Exception):
    """Un problema con la edición, explicado para quien llena el archivo."""


def cargar(carpeta: Path) -> Edicion:
    """Lee y valida la edición; también comprueba la carpeta y las fotos."""
    carpeta = Path(carpeta)
    datos = _leer_toml(carpeta / ARCHIVO)
    try:
        edicion = Edicion.model_validate(datos)
    except ValidationError as e:
        raise ErrorEdicion(describir_error(e, datos)) from None

    if carpeta.name != edicion.semestre:
        raise ErrorEdicion(
            f"La carpeta se llama «{carpeta.name}» pero {ARCHIVO} dice "
            f'semestre = "{edicion.semestre}". Deben coincidir.'
        )

    # Se compara el nombre exacto: Windows no distingue mayúsculas y Linux sí, así
    # que una foto que «funciona» en un computador podría faltar en otro.
    carpeta_fotos = carpeta / "fotos"
    presentes = {p.name for p in carpeta_fotos.iterdir()} if carpeta_fotos.is_dir() else set()
    faltan = [n for n in fotos_nombradas(edicion) if n not in presentes]
    if faltan:
        raise ErrorEdicion(
            f"Faltan estas fotos en {carpeta_fotos} (el nombre debe coincidir exacto, "
            f"con mayúsculas y extensión): {', '.join(faltan)}"
        )
    return edicion


def nueva(base: Path, semestre: str) -> Path:
    """Crea la carpeta del semestre con la estructura de la edición anterior."""
    base = Path(base)
    partes = _SEMESTRE.match(semestre)
    if not partes:
        raise ErrorEdicion(
            f"El semestre «{semestre}» no es válido: usa la forma AAAA-1 o AAAA-2, "
            "por ejemplo 2026-2."
        )
    carpeta = base / semestre
    if carpeta.exists():
        raise ErrorEdicion(f"La edición {semestre} ya existe en {carpeta}; no se sobrescribe.")

    existentes = _ediciones_en(base)
    volumenes = [d.get("volumen", 0) for d in existentes.values()] + _volumenes_anteriores(base)
    volumen = max(volumenes, default=0) + 1
    fecha = f"{'Junio' if partes.group(2) == '1' else 'Diciembre'} {partes.group(1)}"

    previas = sorted(s for s in existentes if s < semestre)
    if previas:
        texto = tomli_w.dumps(_estructura(existentes[previas[-1]], volumen, semestre, fecha))
    else:
        # El esqueleto se copia como texto para conservar sus comentarios de ayuda.
        texto = (
            ESQUELETO.read_text(encoding="utf-8")
            .replace("{volumen}", str(volumen))
            .replace("{semestre}", semestre)
            .replace("{fecha}", fecha)
        )

    (carpeta / "fotos").mkdir(parents=True)
    (carpeta / ARCHIVO).write_text(texto, encoding="utf-8")
    return carpeta


def describir_error(error: ValidationError, datos: dict) -> str:
    """Traduce los errores de validación a algo que se pueda corregir en el archivo."""
    lineas = [_describir(e, datos) for e in error.errors()]
    return f"Hay errores en {ARCHIVO}:\n" + "\n".join(f"- {linea}" for linea in lineas)


def _describir(error: dict, datos: dict) -> str:
    ruta = list(error["loc"])
    lugar = "General"
    if len(ruta) >= 2 and ruta[0] == "secciones" and isinstance(ruta[1], int):
        indice = ruta[1]
        secciones = datos.get("secciones") or []
        seccion = secciones[indice] if indice < len(secciones) else {}
        seccion = seccion if isinstance(seccion, dict) else {}
        lugar = f"Sección {indice + 1} («{seccion.get('titulo', 'sin título')}»)"
        ruta = ruta[2:]
        # pydantic antepone el tipo de la sección a la ruta del campo; no aporta nada.
        if ruta and ruta[0] == seccion.get("tipo"):
            ruta = ruta[1:]
    elif ruta and ruta[0] in _SECCIONES_GENERALES:
        lugar = str(ruta[0]).capitalize()
        ruta = ruta[1:]

    campo = _ruta(ruta)
    explicacion = _explicar(error)
    return f"{lugar}, campo {campo}: {explicacion}" if campo else f"{lugar}: {explicacion}"


def _ruta(partes: list) -> str:
    texto = ""
    for parte in partes:
        if isinstance(parte, int):
            texto += f"[{parte}]"
        else:
            texto += ("." if texto else "") + str(parte)
    return texto


def _explicar(error: dict) -> str:
    tipo = error["type"]
    contexto = error.get("ctx", {})
    valor = error.get("input")
    match tipo:
        case "union_tag_invalid":
            return (
                f"el tipo «{contexto.get('tag')}» no existe; usa uno de estos: "
                f"{', '.join(TIPOS_DE_SECCION)}"
            )
        case "union_tag_not_found":
            return f"falta el campo tipo; usa uno de estos: {', '.join(TIPOS_DE_SECCION)}"
        case "missing":
            return "falta este campo"
        case "extra_forbidden":
            return "este campo no existe (¿está bien escrito?)"
        case "less_than_equal":
            return f"vale {valor} y debe ser como máximo {contexto.get('le')}"
        case "greater_than_equal":
            return f"vale {valor} y debe ser como mínimo {contexto.get('ge')}"
        case "string_pattern_mismatch":
            return f"«{valor}» debe tener la forma AAAA-1 o AAAA-2, por ejemplo 2026-2"
        case "too_long":
            return f"tiene demasiados elementos (máximo {contexto.get('max_length')})"
        case "string_type":
            return "debe ser un texto entre comillas"
        case "int_type" | "int_parsing" | "float_type" | "float_parsing":
            return f"«{valor}» debe ser un número"
        case "value_error":
            return str(contexto.get("error", error["msg"]))
        case _:
            return error["msg"]


def _leer_toml(archivo: Path) -> dict:
    try:
        with archivo.open("rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        raise ErrorEdicion(f"No existe {archivo}.") from None
    except tomllib.TOMLDecodeError as e:
        linea = re.search(r"line (\d+)", str(e))
        donde = f"línea {linea.group(1)}" if linea else "posición desconocida"
        raise ErrorEdicion(f"{archivo.name}, {donde}: no es un TOML válido ({e}).") from None


def _ediciones_en(base: Path) -> dict[str, dict]:
    if not base.is_dir():
        return {}
    return {
        p.name: _leer_toml(p / ARCHIVO)
        for p in base.iterdir()
        if p.is_dir() and _SEMESTRE.match(p.name) and (p / ARCHIVO).is_file()
    }


def _volumenes_anteriores(base: Path) -> list[int]:
    archivo = base / "anteriores.toml"
    if not archivo.is_file():
        return []
    return [a.get("volumen", 0) for a in _leer_toml(archivo).get("anteriores", [])]


def _estructura(datos: dict, volumen: int, semestre: str, fecha: str) -> dict:
    """La edición anterior sin su contenido: mismas secciones, todas pendientes."""
    editorial = datos.get("editorial", {})
    return {
        "volumen": volumen,
        "semestre": semestre,
        "fecha": fecha,
        "estado": "borrador",
        "portada": {"titular": ""},
        "editorial": {
            "titulo": editorial.get("titulo", ""),
            "cuerpo": "",
            "firma": editorial.get("firma", ""),
        },
        "secciones": [
            {
                "tipo": s["tipo"],
                "etiqueta": s["etiqueta"],
                "titulo": s["titulo"],
                "pendiente": "Falta el contenido de este semestre.",
            }
            for s in datos.get("secciones", [])
        ],
    }
