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
from boletin_empleos.render.web import renderizar_web
from boletin_empleos.verificacion import filtrar_enlaces_vivos

_log = logging.getLogger("boletin")


# Cada carrera declara en su archivo cuáles usa: Remotive y Remote OK son
# bolsas de vacantes de tecnología y no tienen nada que ofrecerle a Ingeniería
# Industrial.
def construir_fuentes(cfg: Config) -> list[FuenteEmpleo]:
    disponibles = {
        "spe": lambda: FuenteSPE(consultas=cfg.fuentes.consultas()),
        "magneto": lambda: FuenteMagneto(rutas=cfg.fuentes.rutas_magneto),
        "remotive": FuenteRemotive,
        "remoteok": FuenteRemoteOK,
    }
    fuentes = []
    for nombre in cfg.fuentes.usar:
        crear = disponibles.get(nombre)
        if crear is None:
            _log.warning("fuente desconocida en la configuración: %s", nombre)
            continue
        fuentes.append(crear())
    return fuentes


def _ruta_config(programa: str) -> Path:
    return Path("programas") / f"{programa}.toml"


def _rutas_de_datos(clave: str) -> tuple[Path, Path]:
    """Cada carrera archiva lo suyo aparte: (ediciones, historial)."""
    raiz = Path("datos") / clave
    return raiz / "ediciones", raiz / "historial.json"


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
    p.add_argument(
        "--programa",
        default="software",
        help="carrera del boletín; busca programas/<nombre>.toml",
    )
    p.add_argument("--config", type=Path, default=None, help="ruta explícita a la configuración")
    p.add_argument("--historial", type=Path, default=None)
    p.add_argument("--salida", type=Path, default=None)
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
    ruta_config = args.config or _ruta_config(args.programa)
    try:
        cfg = cargar_config(ruta_config)
    except (OSError, tomllib.TOMLDecodeError, ValidationError) as e:
        # Archivo ausente, TOML ilegible o campo obligatorio faltante: se nombra
        # el archivo para que quien lea el log sepa cuál revisar.
        _log.error("no se pudo cargar la configuración desde %s: %s", ruta_config, e)
        return 1

    # Manda la clave del archivo, no la del argumento: así una carrera no puede
    # terminar escribiendo en la carpeta de otra por un typo en la invocación.
    salida_por_defecto, historial_por_defecto = _rutas_de_datos(cfg.clave)
    args.salida = args.salida or salida_por_defecto
    args.historial = args.historial or historial_por_defecto
    _log.info("boletín de %s", cfg.programa)

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
    hoy = date.today()

    entrega = _crear_entrega(args, cfg, hoy)
    if entrega is None:
        return 1
    ofertas = []
    fuentes_usadas: list[FuenteUsada] = []
    fuentes_caidas: list[str] = []
    confianza_por_fuente: dict[str, float] = {}

    for fuente in construir_fuentes(cfg):
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

    enriquecedor = crear_enriquecedor(os.environ.get("ANTHROPIC_API_KEY"), cfg.programa)
    datos = DatosBoletin(
        programa=cfg.programa,
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
    url_edicion = _url_edicion(cfg, hoy)
    url_logo = _url_logo(cfg)
    try:
        # Dos piezas distintas para dos medios distintos: la web puede usar la
        # identidad completa de la universidad; el correo tiene que sobrevivir a
        # clientes que apenas entienden tablas.
        html = renderizar_web(datos)
        html_correo = renderizar(
            datos.model_copy(
                update={
                    "url_edicion": url_edicion,
                    "url_logo": url_logo,
                    "tope_vacantes": cfg.sitio.vacantes_en_correo if url_edicion else None,
                }
            )
        )
    except Exception as e:  # render no documenta un contrato "nunca lanza"
        _log.error("fallo al renderizar el boletín: %s", e)
        return 1

    # La edición completa se archiva siempre, también en vista previa: es el
    # archivo que publica el sitio y al que apunta el enlace del correo.
    args.salida.mkdir(parents=True, exist_ok=True)
    (args.salida / f"{hoy.isoformat()}.html").write_text(html, encoding="utf-8")

    if not entrega.enviar(cfg.asunto, html_correo, cfg.destinatarios):
        return 1

    if args.dry_run:
        # El historial NO se toca: si se registrara, las ofertas vistas en la prueba
        # se darían por enviadas y la directora nunca las recibiría en la edición real.
        _log.info("dry-run: vista previa con %d vacantes; historial sin cambios", len(vivas))
        return 0

    historial.registrar({e.oferta.id for e in vivas}, hoy)
    _log.info("edición %d completada con %d vacantes", datos.numero_edicion, len(vivas))
    return 0


def _url_edicion(cfg: Config, hoy: date) -> str | None:
    """Dónde quedará publicada esta edición. Sin sitio configurado, no hay enlace."""
    if not cfg.sitio.url_base:
        return None
    return f"{cfg.sitio.url_base.rstrip('/')}/{cfg.clave}/ediciones/{hoy.isoformat()}.html"


def _url_logo(cfg: Config) -> str | None:
    """El escudo lo sirve el propio sitio; sin sitio, el correo va sin imagen."""
    if not cfg.sitio.url_base:
        return None
    return f"{cfg.sitio.url_base.rstrip('/')}/logo-humboldt.png"


def _crear_entrega(
    args: argparse.Namespace, cfg: Config, hoy: date
) -> EntregaConsola | EntregaSMTP | None:
    if args.dry_run:
        # Nombre explícito: en la misma carpeta queda la edición completa del día.
        return EntregaConsola(args.salida, f"{hoy.isoformat()}-correo.html")

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
