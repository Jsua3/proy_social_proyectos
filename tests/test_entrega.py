from boletin_empleos.entrega.consola import EntregaConsola
from boletin_empleos.entrega.smtp import EntregaSMTP


def test_consola_guarda_el_html_en_disco(tmp_path):
    entrega = EntregaConsola(tmp_path)
    assert entrega.enviar("Asunto", "<html>hola</html>", ["a@b.co"]) is True

    archivos = list(tmp_path.glob("*.html"))
    assert len(archivos) == 1
    assert archivos[0].read_text("utf-8") == "<html>hola</html>"


def test_smtp_arma_un_mensaje_valido(monkeypatch):
    enviados = {}

    class ServidorFalso:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            enviados["tls"] = True

        def login(self, usuario, clave):
            enviados["login"] = usuario

        def send_message(self, mensaje):
            enviados["mensaje"] = mensaje

    monkeypatch.setattr("smtplib.SMTP", lambda host, puerto, timeout=30: ServidorFalso())

    entrega = EntregaSMTP(
        host="smtp.ejemplo.co",
        puerto=587,
        usuario="cuenta@cue.edu.co",
        clave="secreta",
        remitente="cuenta@cue.edu.co",
    )
    assert entrega.enviar("Boletín", "<html>x</html>", ["dir@cue.edu.co"]) is True

    assert enviados["tls"] is True
    mensaje = enviados["mensaje"]
    assert mensaje["Subject"] == "Boletín"
    assert mensaje["To"] == "dir@cue.edu.co"
    assert "<html>x</html>" in mensaje.get_content()


def test_smtp_devuelve_false_si_falla(monkeypatch):
    def explotar(*a, **k):
        raise OSError("sin conexión")

    monkeypatch.setattr("smtplib.SMTP", explotar)

    entrega = EntregaSMTP("h", 587, "u", "c", "u@cue.edu.co")
    assert entrega.enviar("Boletín", "<html>x</html>", ["dir@cue.edu.co"]) is False
