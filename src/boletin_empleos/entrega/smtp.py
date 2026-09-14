"""Entrega por SMTP institucional."""

import logging
import smtplib
from email.message import EmailMessage

_log = logging.getLogger(__name__)


class EntregaSMTP:
    def __init__(self, host: str, puerto: int, usuario: str, clave: str, remitente: str) -> None:
        self._host = host
        self._puerto = puerto
        self._usuario = usuario
        self._clave = clave
        self._remitente = remitente

    def enviar(self, asunto: str, html: str, destinatarios: list[str]) -> bool:
        mensaje = EmailMessage()
        mensaje["Subject"] = asunto
        mensaje["From"] = self._remitente
        mensaje["To"] = ", ".join(destinatarios)
        mensaje.set_content(html, subtype="html")

        try:
            with smtplib.SMTP(self._host, self._puerto, timeout=30) as servidor:
                servidor.starttls()
                servidor.login(self._usuario, self._clave)
                servidor.send_message(mensaje)
        except (OSError, smtplib.SMTPException) as e:
            _log.error("no se pudo enviar el boletín: %s", e)
            return False

        _log.info("boletín enviado a %s", ", ".join(destinatarios))
        return True
