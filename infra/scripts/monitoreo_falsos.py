"""Dobles de prueba del monitoreo: un buzón SMTP y unas métricas protegidas con token.

`python monitoreo_falsos.py smtp`      escucha en :25 y escribe cada correo recibido en la salida.
`python monitoreo_falsos.py metricas`  sirve /metrics en :8000 solo con «Authorization: Bearer prueba».
"""

import email
import socketserver
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Smtp(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        def responder(linea: str) -> None:
            self.wfile.write((linea + "\r\n").encode())

        responder("220 buzon.prueba")
        destinos: list[str] = []
        while linea := self.rfile.readline().decode(errors="replace").rstrip("\r\n"):
            orden = linea[:4].upper()
            if orden in ("EHLO", "HELO"):
                responder("250 buzon.prueba")
            elif orden == "RCPT":
                destinos.append(linea)
                responder("250 ok")
            elif orden == "DATA":
                responder("354 adelante")
                cuerpo = []
                while (parte := self.rfile.readline().decode(errors="replace")) != ".\r\n":
                    cuerpo.append(parte)
                mensaje = email.message_from_string("".join(cuerpo))
                texto = "".join(
                    p.get_payload(decode=True).decode(errors="replace")
                    for p in mensaje.walk()
                    if p.get_content_type().startswith("text/")
                )
                asunto = str(email.header.make_header(email.header.decode_header(mensaje["Subject"])))
                print(f"CORREO para={destinos} asunto={asunto}\n{texto}\nFIN-CORREO", flush=True)
                responder("250 recibido")
            elif orden == "QUIT":
                responder("221 adios")
                return
            else:
                responder("250 ok")


class Metricas(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.headers.get("Authorization") != "Bearer prueba":
            self.send_response(401)
            self.end_headers()
            return
        cuerpo = b"# TYPE medtender_documentos_en_proceso_mas_de_1h gauge\nmedtender_documentos_en_proceso_mas_de_1h 0\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *_) -> None:
        pass


if __name__ == "__main__":
    if sys.argv[1] == "smtp":
        socketserver.ThreadingTCPServer(("0.0.0.0", 25), Smtp).serve_forever()
    else:
        ThreadingHTTPServer(("0.0.0.0", 8000), Metricas).serve_forever()
