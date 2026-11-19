"""Contexto de la petición en curso, accesible desde logs y auditoría sin pasar parámetros."""

from contextvars import ContextVar

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
ip_cliente: ContextVar[str | None] = ContextVar("ip_cliente", default=None)
usuario_id: ContextVar[str | None] = ContextVar("usuario_id", default=None)
tenant_id: ContextVar[str | None] = ContextVar("tenant_id", default=None)
