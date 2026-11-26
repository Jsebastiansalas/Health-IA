"""Logging estructurado.

En producción cada línea es un objeto JSON con request_id, usuario y tenant, lo que permite
seguir una petición de punta a punta. Nunca se registran cuerpos de petición, contraseñas,
tokens ni el contenido de los documentos o de las preguntas.
"""

import json
import logging
import sys
from datetime import UTC, datetime

from app.core import contexto

_ATRIBUTOS_ESTANDAR = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class FormatoJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        linea = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
        }
        for clave, valor in (
            ("request_id", contexto.request_id.get()),
            ("usuario_id", contexto.usuario_id.get()),
            ("tenant_id", contexto.tenant_id.get()),
        ):
            if valor:
                linea[clave] = valor
        # Campos pasados con logger.info(..., extra={...}).
        for clave, valor in record.__dict__.items():
            if clave not in _ATRIBUTOS_ESTANDAR and not clave.startswith("_"):
                linea[clave] = valor
        if record.exc_info:
            linea["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(linea, ensure_ascii=False, default=str)


class FormatoTexto(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        rid = contexto.request_id.get()
        prefijo = f"[{rid[:8]}] " if rid else ""
        base = f"{self.formatTime(record)} {record.levelname} [{record.name}] {prefijo}"
        texto = base + record.getMessage()
        if record.exc_info:
            texto += "\n" + self.formatException(record.exc_info)
        return texto


def configurar_logging(en_json: bool, nivel: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(FormatoJson() if en_json else FormatoTexto())
    handler._medtender = True  # type: ignore[attr-defined]
    raiz = logging.getLogger()
    # Idempotente: reemplaza solo el handler propio de una configuración anterior y respeta los
    # ajenos (pytest, un agente de errores...).
    raiz.handlers[:] = [h for h in raiz.handlers if not getattr(h, "_medtender", False)]
    raiz.addHandler(handler)
    raiz.setLevel(nivel)
    # Los access logs de uvicorn duplicarían los propios (con request_id y duración).
    logging.getLogger("uvicorn.access").disabled = True
    # httpx registra la URL completa de cada petición; con la API key en cabecera no hay fuga,
    # pero el ruido no aporta.
    logging.getLogger("httpx").setLevel(logging.WARNING)
