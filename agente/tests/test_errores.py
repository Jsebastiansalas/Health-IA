"""El rastreo de errores no puede llevarse datos de salud: se revisan los bytes que de verdad salen."""

import gzip
import json
import logging
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import sentry_sdk

from app.core import errores


@pytest.fixture
def colector():
    recibidos: list[bytes] = []

    class Manejador(BaseHTTPRequestHandler):
        def do_POST(self):
            cuerpo = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if self.headers.get("Content-Encoding") == "gzip":
                cuerpo = gzip.decompress(cuerpo)
            elif self.headers.get("Content-Encoding") == "br":
                import brotli

                cuerpo = brotli.decompress(cuerpo)
            recibidos.append(cuerpo)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *_):
            pass

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    dsn = f"http://claveinventada@127.0.0.1:{servidor.server_port}/1"
    yield dsn, recibidos
    errores.apagar()
    servidor.shutdown()


def _falla_con_datos():
    nombre_del_paciente = "Ana Pérez Variable"  # una variable local: no debe viajar
    raise ValueError(f"No se encontró la hemoglobina de {nombre_del_paciente} (13,2 g/dL)")


def _enviado(recibidos) -> str:
    sentry_sdk.flush(timeout=5)
    return "\n".join(r.decode("utf-8", errors="replace") for r in recibidos)


def test_solo_viaja_el_tipo_y_por_donde_paso(colector):
    dsn, recibidos = colector
    assert errores.configurar(dsn, "agente", "produccion")
    log = logging.getLogger("medtender.prueba")
    sentry_sdk.set_user({"email": "ana@correo.co"})
    sentry_sdk.set_tag("pregunta", "¿qué tomo para la tensión?")
    sentry_sdk.set_context("expediente", {"titulo": "Historia de Ana"})
    sentry_sdk.add_breadcrumb(message="subió historia_clinica_ana.pdf")
    try:
        _falla_con_datos()
    except ValueError:
        log.exception("Falló la consulta de %s", "ana@correo.co")

    todo = _enviado(recibidos)
    assert "ValueError" in todo and "_falla_con_datos" in todo and "test_errores.py" in todo
    for prohibido in (
        "Ana", "ana@correo.co", "hemoglobina", "13,2", "tensi", "historia_clinica", "Historia",
        "nombre_del_paciente", "Falló la consulta", socket.gethostname(), "raise ValueError",
    ):
        assert prohibido not in todo, prohibido
    evento = next(json.loads(x) for x in todo.splitlines() if '"exception"' in x)
    assert set(evento) <= {
        "event_id", "timestamp", "platform", "level", "environment", "release", "sdk",
        "server_name", "exception", "tags",
    }
    assert evento["server_name"] == "agente" and evento["tags"] == {"servicio": "agente"}


def test_la_causa_encadenada_tambien_va_sin_su_mensaje(colector):
    dsn, recibidos = colector
    errores.configurar(dsn, "worker", "produccion")
    try:
        try:
            _falla_con_datos()
        except ValueError as exc:
            raise RuntimeError("documento de Ana Pérez ilegible") from exc
    except RuntimeError:
        logging.getLogger("medtender.prueba").exception("x")
    todo = _enviado(recibidos)
    assert "RuntimeError" in todo and "ValueError" in todo and "Ana" not in todo


def test_sin_dsn_no_se_envia_nada():
    assert not errores.configurar("", "agente", "produccion")


def test_un_aviso_sin_excepcion_no_se_reporta(colector):
    dsn, recibidos = colector
    errores.configurar(dsn, "agente", "produccion")
    logging.getLogger("medtender.prueba").error("algo sobre Ana Pérez")
    assert _enviado(recibidos) == ""
