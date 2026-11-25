"""Rastreo de errores (GlitchTip o cualquier servicio compatible con Sentry), sin datos de salud.

Un error arrastra por naturaleza lo que no debe salir: su mensaje, las variables, la petición, las
migas. Por eso hay dos barreras:
1. El SDK no recoge nada por su cuenta: sin integraciones, sin migas, sin variables ni líneas de
   código.
2. `limpiar` no «quita lo sensible»: **construye un evento nuevo solo con lo permitido** (tipo del
   error, archivo, función y línea). Lo que una versión futura del SDK añada tampoco pasa.

Solo se reporta lo que el código registra con excepción (`log.exception`, `exc_info`). Sin
`ERRORES_DSN` está apagado.
"""

import logging

import sentry_sdk

_PERMITIDO = ("event_id", "timestamp", "platform", "level", "environment", "release", "sdk")
_MARCO = ("filename", "function", "module", "lineno", "in_app")
_REGISTRADORES = ("", "uvicorn.error", "arq")  # ni uvicorn ni arq propagan a la raíz

_servicio = ""


def limpiar(evento: dict, _pista: dict) -> dict | None:
    excepciones = (evento.get("exception") or {}).get("values") or []
    if not excepciones:
        return None  # sin excepción no hay nada seguro que contar
    limpio = {k: evento[k] for k in _PERMITIDO if k in evento}
    limpio["server_name"] = _servicio  # no el nombre de la máquina
    limpio["tags"] = {"servicio": _servicio}
    limpio["exception"] = {
        "values": [
            {
                "type": e.get("type"),
                "module": e.get("module"),
                "value": "",  # el mensaje puede traer texto de documentos o nombres
                "stacktrace": {
                    "frames": [
                        {k: m[k] for k in _MARCO if k in m}
                        for m in (e.get("stacktrace") or {}).get("frames", [])
                    ]
                },
            }
            for e in excepciones
        ]
    }
    return limpio


class _ReportarExcepciones(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.ERROR)

    def emit(self, record: logging.LogRecord) -> None:
        # Del registro solo se toma la excepción, nunca el texto.
        if record.exc_info and record.exc_info[1] and not record.name.startswith("sentry_sdk"):
            sentry_sdk.capture_exception(record.exc_info[1])


_manejador = _ReportarExcepciones()


def configurar(dsn: str, servicio: str, entorno: str) -> bool:
    """Activa el rastreo si hay DSN. Devuelve si quedó activo."""
    global _servicio
    if not dsn:
        return False
    _servicio = servicio
    sentry_sdk.init(
        dsn=dsn,
        environment=entorno,
        default_integrations=False,
        auto_enabling_integrations=False,
        max_breadcrumbs=0,
        traces_sample_rate=0,
        auto_session_tracking=False,
        send_client_reports=False,
        data_collection={
            "user_info": False,
            "http_bodies": [],
            "database_query_data": False,
            "queues": False,
            "stack_frame_variables": False,
            "frame_context_lines": 0,
        },
        before_send=limpiar,
    )
    for nombre in _REGISTRADORES:
        registrador = logging.getLogger(nombre)
        if _manejador not in registrador.handlers:
            registrador.addHandler(_manejador)
    return True


def apagar() -> None:
    for nombre in _REGISTRADORES:
        logging.getLogger(nombre).removeHandler(_manejador)
    sentry_sdk.get_client().close(timeout=2)
