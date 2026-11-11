"""Consola del boletín semestral: `semestral nueva`, `semestral armar` y `semestral borrador`."""

import argparse
import os
import sys
from pathlib import Path

from boletin_semestral.armado import armar
from boletin_semestral.borrador import Redactor, escribir_sugerencias
from boletin_semestral.edicion import ErrorEdicion, cargar, nueva
from boletin_semestral.pdf import ChromiumAusente

DATOS = Path("datos/semestral")
SALIDA = Path("salida/semestral")


def main(argv: list[str] | None = None) -> int:
    # En Windows, una salida por tubería (Git Bash) usa cp1252 y rompe las tildes.
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        prog="semestral", description="Boletín semestral de proyección social"
    )
    comandos = parser.add_subparsers(dest="comando", required=True)

    p_nueva = comandos.add_parser("nueva", help="Crea la edición de un semestre")
    p_nueva.add_argument("semestre", help="AAAA-1 o AAAA-2, por ejemplo 2026-2")
    p_nueva.add_argument("--datos", type=Path, default=DATOS)

    p_armar = comandos.add_parser("armar", help="Genera la vista previa o la edición publicada")
    p_armar.add_argument("semestre", help="AAAA-1 o AAAA-2, por ejemplo 2026-2")
    p_armar.add_argument("--datos", type=Path, default=DATOS)
    p_armar.add_argument("--salida", type=Path, default=SALIDA)

    p_borrador = comandos.add_parser(
        "borrador", help="Opcional: Claude propone textos a partir del correo de la Coordinación"
    )
    p_borrador.add_argument("semestre", help="AAAA-1 o AAAA-2, por ejemplo 2026-2")
    p_borrador.add_argument("--correo", type=Path, required=True, help="Texto del correo (.txt)")
    p_borrador.add_argument("--datos", type=Path, default=DATOS)

    args = parser.parse_args(argv)
    try:
        if args.comando == "nueva":
            return _nueva(args)
        if args.comando == "borrador":
            return _borrador(args)
        return _armar(args)
    except (ErrorEdicion, ChromiumAusente) as e:
        print(e, file=sys.stderr)
        return 1


def _nueva(args: argparse.Namespace) -> int:
    carpeta = nueva(args.datos, args.semestre)
    print(f"Edición creada en {carpeta}.")
    print(f"Llena {carpeta / 'edicion.toml'} y copia las fotos en {carpeta / 'fotos'}.")
    return 0


def _borrador(args: argparse.Namespace) -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "Falta ANTHROPIC_API_KEY; el resto del programa funciona sin este paso.",
            file=sys.stderr,
        )
        return 1
    if not args.correo.is_file():
        print(f"No existe el archivo del correo: {args.correo}", file=sys.stderr)
        return 1

    carpeta = args.datos / args.semestre
    sugerencias = Redactor().proponer(args.correo.read_text(encoding="utf-8"), cargar(carpeta))
    if sugerencias is None:
        print(
            "No se pudo obtener una propuesta de Claude; el resto del programa funciona "
            "sin este paso.",
            file=sys.stderr,
        )
        return 1

    destino = carpeta / "borrador-sugerido.toml"
    escribir_sugerencias(sugerencias, destino)
    print(f"Propuestas guardadas en {destino}. Copia a edicion.toml lo que sirva.")
    return 0


def _armar(args: argparse.Namespace) -> int:
    r = armar(args.datos / args.semestre, args.salida)
    print(f"{'Edición publicada' if r.publicada else 'Vista previa'}: {r.destino / 'index.html'}")
    print(f"PDF: {r.pdf}")
    if r.reducidas:
        print(f"Fotos reducidas: {', '.join(r.reducidas)}")
    if r.pequenas:
        print(f"Fotos pequeñas (se verán borrosas): {', '.join(r.pequenas)}")
    if r.largas:
        largas = ", ".join(f"{titulo} ({n} páginas)" for titulo, n in r.largas)
        print(f"Secciones de más de una página: {largas}")
    if r.pendientes:
        print(f"Pendientes ({len(r.pendientes)}):")
        for p in r.pendientes:
            print(f"- {p.lugar}: {p.motivo}")
    else:
        print("Sin pendientes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
