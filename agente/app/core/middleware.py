"""Middleware ASGI puro (sin BaseHTTPMiddleware).

Por cada petición HTTP:
1. Asigna request_id (se respeta el de Caddy si es válido) y lo devuelve en X-Request-ID.
2. Determina la IP real del cliente.
3. Añade cabeceras de seguridad a las respuestas de la API (Cache-Control: no-store: las
   respuestas contienen datos confidenciales y no deben quedar en cachés).
4. Registra un log de acceso y las métricas HTTP.
"""

import logging
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core import contexto
from app.core.config import get_settings
from app.core.metricas import HTTP_DURACION, HTTP_SOLICITUDES

log = logging.getLogger("medtender.acceso")

_ID_VALIDO = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def ip_del_cliente(scope: Scope, headers: Headers) -> str:
    if get_settings().confiar_proxy:
        reenviado = headers.get("x-forwarded-for")
        if reenviado:
            # Caddy añade la IP que vio al final; las anteriores las puede falsear el cliente.
            return reenviado.split(",")[-1].strip()
    cliente = scope.get("client")
    return cliente[0] if cliente else "desconocida"


def plantilla_de_ruta(scope: Scope) -> str:
    """'/api/v1/expedientes/{expediente_id}' en vez de la URL con el id real.

    Los ids no pueden ir en las etiquetas de métricas (cardinalidad infinita) ni en los logs de
    acceso. FastAPI guarda el prefijo del router fuera de `route.path`, así que la plantilla se
    reconstruye desde la URL: cada segmento que coincide con un parámetro de ruta se sustituye
    por su nombre. Una ruta que no existe se agrupa en '/otros'.
    """
    if scope.get("route") is None:
        return "/otros"
    pendientes = [(str(v), k) for k, v in (scope.get("path_params") or {}).items()]
    segmentos = []
    for segmento in scope["path"].split("/"):
        for i, (valor, nombre) in enumerate(pendientes):
            if segmento == valor:
                segmento = "{" + nombre + "}"
                del pendientes[i]
                break
        segmentos.append(segmento)
    return "/".join(segmentos)


class MiddlewareSolicitud:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        entrante = headers.get("x-request-id", "")
        rid = entrante if _ID_VALIDO.match(entrante) else uuid.uuid4().hex
        ip = ip_del_cliente(scope, headers)
        tokens = [
            (contexto.request_id, contexto.request_id.set(rid)),
            (contexto.ip_cliente, contexto.ip_cliente.set(ip)),
            (contexto.usuario_id, contexto.usuario_id.set(None)),
            (contexto.tenant_id, contexto.tenant_id.set(None)),
        ]
        inicio = time.perf_counter()
        codigo = 500
        es_api = scope["path"].startswith("/internal/")

        async def enviar(mensaje: Message) -> None:
            nonlocal codigo
            if mensaje["type"] == "http.response.start":
                codigo = mensaje["status"]
                h = MutableHeaders(scope=mensaje)
                h["X-Request-ID"] = rid
                h["X-Content-Type-Options"] = "nosniff"
                if es_api:
                    h["Cache-Control"] = "no-store"
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        finally:
            self._registrar(scope, codigo, time.perf_counter() - inicio)
            for var, token in reversed(tokens):
                var.reset(token)

    @staticmethod
    def _registrar(scope: Scope, codigo: int, duracion_s: float) -> None:
        ruta = plantilla_de_ruta(scope)
        metodo = scope["method"]
        HTTP_SOLICITUDES.labels(metodo, ruta, str(codigo)).inc()
        HTTP_DURACION.labels(metodo, ruta).observe(duracion_s)
        if scope["path"] == "/health" and codigo == 200:
            return  # las sondas de salud inundarían el log
        nivel = logging.WARNING if codigo >= 500 else logging.INFO
        log.log(
            nivel,
            "%s %s %d %.0f ms",
            metodo,
            ruta,
            codigo,
            duracion_s * 1000,
            extra={
                "metodo": metodo,
                "ruta": ruta,
                "codigo": codigo,
                "duracion_ms": round(duracion_s * 1000),
            },
        )
