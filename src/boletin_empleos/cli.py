"""Punto de entrada. Este archivo es lo único que GitHub Actions invoca.

Códigos de salida:
  0  boletín generado y entregado
  1  error de configuración, de argumentos, de render o de entrega
  2  ninguna fuente respondió — no se envía boletín vacío (spec §12)
  3  no hay ofertas nuevas para esta edición

`--dry-run` es una vista previa: deja el HTML en --salida y NO modifica el historial.
"""

import argparse
import logging
import os
import sys
import tomllib
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from boletin_empleos.almacenamiento import HistorialIlegible
from boletin_empleos.almacenamiento.json_repo import HistorialJSON
from boletin_empleos.config import Config, cargar_config
from boletin_empleos.enriquecimiento import crear_enriquecedor
from boletin_empleos.entrega.consola import EntregaConsola
from boletin_empleos.entrega.smtp import EntregaSMTP
from boletin_empleos.fuentes.base import FuenteEmpleo
from boletin_empleos.fuentes.magneto import FuenteMagneto
from boletin_empleos.fuentes.remoteok import FuenteRemoteOK
from boletin_empleos.fuentes.remotive import FuenteRemotive
from boletin_empleos.fuentes.spe import FuenteSPE
from boletin_empleos.nucleo.pipeline import evaluar
from boletin_empleos.render.renderizador import DatosBoletin, FuenteUsada, renderizar
from boletin_empleos.verificacion import filtrar_enlaces_vivos

_log = logging.getLogger("boletin")


def construir_fuentes() -> list[FuenteEmpleo]:
    return [FuenteSPE(), FuenteMagneto(), FuenteRemotive(), FuenteRemoteOK()]


class _ArgumentParser(argparse.ArgumentParser):
    """Un typo en un flag no debe salir con el mismo código que una degradación real.

    argparse sale con 2 por defecto ante argumentos inválidos, el mismo código
    que usa esta app para "ninguna fuente respondió" (spec §12). Un error de
    invocación del workflow y una caída real de fuentes deben distinguirse.
    """

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    p = _ArgumentParser(prog="boletin", description="Boletín quincenal de empleos")
    p.add_argument("--dry-run", action="store_true", help="renderiza y guarda en disco sin enviar")
    p.add_argument("--config", type=Path, default=Path("config.toml"))
    p.add_argument("--historial", type=Path, default=Path("datos/historial.json"))
    p.add_argument("--salida", type=Path, default=Path("datos/ediciones"))
    p.add_argument("--verboso", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verboso else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return ejecutar(args)


def ejecutar(args: argparse.Namespace) -> int:
    try:
        cfg = cargar_config(args.config)
    except (OSError, tomllib.TOMLDecodeError, ValidationError) as e:
        # Archivo ausente, TOML ilegible o campo obligatorio faltante: se nombra
        # el archivo para que quien lea el log sepa cuál revisar.
        _log.error("no se pudo cargar la configuración desde %s: %s", args.config, e)
        return 1

    try:
        historial = HistorialJSON(args.historial)
    except HistorialIlegible as e:
        # Nunca se sigue con un historial vacío: reenviaría todo lo ya enviado.
        _log.error("%s", e)
        return 1

    # La entrega se valida antes de tocar cualquier fuente, enlace o IA: un
    # secreto SMTP roto en el workflow debe fallar rápido y sin costo, no
    # después de recolectar, verificar enlaces y pagar por enriquecer una
    # edición que de todos modos no se va a poder enviar.
    entrega = _crear_entrega(args, cfg)
    if entrega is None:
        return 1

    hoy = date.today()
    ofertas = []
    fuentes_usadas: list[FuenteUsada] = []
    fuentes_caidas: list[str] = []
    confianza_por_fuente: dict[str, float] = {}

    for fuente in construir_fuentes():
        confianza_por_fuente[fuente.nombre] = fuente.confianza_base
        recogidas = fuente.obtener()
        if recogidas:
            ofertas.extend(recogidas)
            fuentes_usadas.append(
                FuenteUsada(
                    nombre=fuente.nombre,
                    atribucion=fuente.atribucion,
                    url_atribucion=fuente.url_atribucion,
                )
            )
            _log.info("%s: %d ofertas", fuente.nombre, len(recogidas))
        else:
            fuentes_caidas.append(fuente.nombre)
            _log.warning("%s: no aportó ofertas en esta edición", fuente.nombre)

    if not fuentes_usadas:
        _log.error("ninguna fuente respondió; no se envía un boletín vacío")
        return 2

    resultado = evaluar(ofertas, historial.ids_enviados(), cfg, confianza_por_fuente, hoy)
    vivas, muertas = filtrar_enlaces_vivos(resultado.incluidas)
    _log.info("conteos: %s | enlaces muertos: %d", resultado.conteos, len(muertas))

    if not vivas:
        _log.warning("no hay ofertas nuevas para esta edición")
        return 3

    enriquecedor = crear_enriquecedor(os.environ.get("ANTHROPIC_API_KEY"))
    datos = DatosBoletin(
        numero_edicion=historial.numero_edicion(),
        fecha=hoy,
        editorial=enriquecedor.editorial(vivas, resultado.conteos),
        incluidas=vivas,
        descartadas=[*resultado.descartadas, *muertas],
        resumenes=enriquecedor.resumir(vivas),
        conteos={**resultado.conteos, "incluidas": len(vivas)},
        fuentes_usadas=fuentes_usadas,
        fuentes_caidas=fuentes_caidas,
    )
    try:
        html = renderizar(datos)
    except Exception as e:  # render no documenta un contrato "nunca lanza"
        _log.error("fallo al renderizar el boletín: %s", e)
        return 1

    if not entrega.enviar(cfg.asunto, html, cfg.destinatarios):
        return 1

    if args.dry_run:
        # EntregaConsola ya dejó el HTML en --salida. El historial NO se toca: si se
        # registrara, las ofertas vistas en la prueba se darían por enviadas y la
        # directora nunca las recibiría en la edición real.
        _log.info("dry-run: vista previa con %d vacantes; historial sin cambios", len(vivas))
        return 0

    args.salida.mkdir(parents=True, exist_ok=True)
    (args.salida / f"{hoy.isoformat()}.html").write_text(html, encoding="utf-8")
    historial.registrar({e.oferta.id for e in vivas}, hoy)
    _log.info("edición %d completada con %d vacantes", datos.numero_edicion, len(vivas))
    return 0


def _crear_entrega(args: argparse.Namespace, cfg: Config) -> EntregaConsola | EntregaSMTP | None:
    if args.dry_run:
        return EntregaConsola(args.salida)

    faltantes = [v for v in ("SMTP_HOST", "SMTP_USUARIO", "SMTP_CLAVE") if not os.environ.get(v)]
    if faltantes:
        _log.error("faltan variables de entorno para el envío: %s", ", ".join(faltantes))
        return None

    return EntregaSMTP(
        host=os.environ["SMTP_HOST"],
        puerto=int(os.environ.get("SMTP_PUERTO", "587")),
        usuario=os.environ["SMTP_USUARIO"],
        clave=os.environ["SMTP_CLAVE"],
        remitente=cfg.remitente,
    )


if __name__ == "__main__":
    sys.exit(main())
