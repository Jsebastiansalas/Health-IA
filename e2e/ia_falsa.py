"""IA de mentira para las pruebas en navegador: imita la API de Gemini sin red ni costo.

No inventa: cita **líneas literales** de los fragmentos que le llegan (lo que de verdad leyó el OCR),
así que la respuesta pasa por las mismas comprobaciones de citas y cifras que la de un modelo real.
Guarda en /peticiones lo último que recibió, para revisar que le llega anonimizado.
"""

import hashlib
import html
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RECIBIDO: list[str] = []


def vector(texto: str) -> list[float]:
    semilla = hashlib.sha256(texto.encode()).digest()
    return [((semilla[i % 32] + i) % 97) / 97 + 0.01 for i in range(1536)]


def fragmentos(prompt: str) -> list[tuple[str, list[str]]]:
    salida = []
    for fid, cuerpo in re.findall(r'<fragmento id="(F\d+)"[^>]*>\n(.*?)\n</fragmento>', prompt, re.S):
        lineas = [" ".join(x.split()) for x in html.unescape(cuerpo).splitlines() if x.strip()]
        salida.append((fid, lineas))
    return salida


def buscar(prompt: str, patron: str) -> tuple[str, str] | None:
    for fid, lineas in fragmentos(prompt):
        for linea in lineas:
            if re.search(patron, linea, re.I):
                return fid, linea
    return None


def vacio(esquema: dict):
    tipo = esquema.get("type", "STRING").upper()
    if tipo == "OBJECT":
        return {k: vacio(v) for k, v in esquema.get("properties", {}).items()}
    return {"ARRAY": [], "BOOLEAN": True, "NUMBER": 0, "INTEGER": 0}.get(tipo, "")


def responder(prompt: str, esquema: dict) -> dict:
    r = vacio(esquema)
    campos = r.keys()
    hemo = buscar(prompt, r"hemoglobina")
    control = buscar(prompt, r"control en")
    fecha = buscar(prompt, r"\d{2}/\d{2}/\d{4}")
    if "hallazgos" in campos and hemo:
        r.update(
            de_que_trata="Resultados de un laboratorio.",
            hallazgos=[{"texto": hemo[1], "fragmento": hemo[0], "extracto_literal": hemo[1]}],
            preguntas_para_el_medico=["¿Cómo debo leer estos resultados?"],
        )
    if "eventos" in campos:
        dia = re.search(r"\d{2}/\d{2}/\d{4}", fecha[1]).group(0) if fecha else ""
        if control:
            r["eventos"].append(
                {"tipo": "CONTROL", "descripcion": control[1], "fecha_texto": "en 3 meses",
                 "fragmento": control[0], "extracto_literal": control[1]}
            )
        if fecha:
            r["eventos"].append(
                {"tipo": "EXAMEN", "descripcion": "Laboratorio clínico", "fecha_texto": dia,
                 "fragmento": fecha[0], "extracto_literal": fecha[1]}
            )
        if hemo:
            r["valores"] = [
                {"analito": "Hemoglobina", "valor": "13,2", "unidad": "g/dL", "rango": "", "marca": "",
                 "fecha_texto": dia, "fragmento": hemo[0], "extracto_literal": hemo[1]}
            ]
    if "preguntas" in campos:
        r["preguntas"] = ["¿Cuándo debo repetir estos exámenes?"]
    if "respuesta" in campos and hemo:
        r.update(respuesta=hemo[1], citas=[{"fragmento": hemo[0], "extracto_literal": hemo[1]}])
    return r


class Gemini(BaseHTTPRequestHandler):
    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        self._json({"textos": RECIBIDO} if self.path == "/peticiones" else {"ok": True})

    def do_POST(self):
        pedido = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path.endswith(":batchEmbedContents"):
            textos = [p["content"]["parts"][0]["text"] for p in pedido["requests"]]
            RECIBIDO.extend(textos)
            return self._json({"embeddings": [{"values": vector(t)} for t in textos]})
        if self.path.endswith(":generateContent"):
            prompt = pedido["contents"][0]["parts"][0]["text"]
            RECIBIDO.append(prompt)
            datos = responder(prompt, pedido["generationConfig"].get("responseSchema", {}))
            return self._json(
                {"candidates": [{"content": {"parts": [{"text": json.dumps(datos)}]}}],
                 "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20}}
            )
        self._json({"error": "ruta desconocida"}, 404)

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9000), Gemini).serve_forever()
