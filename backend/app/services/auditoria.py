"""Registro de auditoría.

Cada evento se guarda con su propia sesión y commit: queda registrado aunque la operación que
lo originó falle o se revierta (p. ej. un acceso denegado) y no depende de la transacción de
la petición. Un fallo al auditar se registra en el log y en una métrica, pero no tumba la
petición del usuario.

Nunca se guarda contenido: ni preguntas, ni textos de documentos, ni contraseñas. Solo
identificadores, roles, motivos y tamaños.
"""

import logging
import uuid
from enum import StrEnum
from typing import Any

from app.core import contexto
from app.core.db import get_sessionmaker
from app.core.metricas import AUDITORIA_FALLOS
from app.models import Auditoria

log = logging.getLogger(__name__)


class Accion(StrEnum):
    LOGIN_OK = "LOGIN_OK"
    LOGIN_FALLIDO = "LOGIN_FALLIDO"
    LOGIN_BLOQUEADO = "LOGIN_BLOQUEADO"
    REGISTRO_TENANT = "REGISTRO_TENANT"
    TENANT_ACTUALIZADO = "TENANT_ACTUALIZADO"
    USUARIO_CREADO = "USUARIO_CREADO"
    USUARIO_ACTUALIZADO = "USUARIO_ACTUALIZADO"
    EXPEDIENTE_CREADO = "EXPEDIENTE_CREADO"
    EXPEDIENTE_ACTUALIZADO = "EXPEDIENTE_ACTUALIZADO"
    EXPEDIENTE_ELIMINADO = "EXPEDIENTE_ELIMINADO"
    PERMISO_ASIGNADO = "PERMISO_ASIGNADO"
    PERMISO_REVOCADO = "PERMISO_REVOCADO"
    ACCESO_DENEGADO = "ACCESO_DENEGADO"
    DOCUMENTO_SUBIDO = "DOCUMENTO_SUBIDO"
    DOCUMENTO_ELIMINADO = "DOCUMENTO_ELIMINADO"
    CONSULTA_RAG = "CONSULTA_RAG"
    REINDEXACION_SOLICITADA = "REINDEXACION_SOLICITADA"


async def auditar(
    accion: Accion,
    *,
    usuario: Any | None = None,  # CurrentUser
    tenant_id: uuid.UUID | None = None,
    usuario_id: uuid.UUID | None = None,
    email: str | None = None,
    resultado: str = "OK",
    recurso_tipo: str | None = None,
    recurso_id: uuid.UUID | None = None,
    detalle: dict | None = None,
) -> None:
    if usuario is not None:
        tenant_id = tenant_id or usuario.tenant_id
        usuario_id = usuario_id or usuario.id
        email = email or usuario.email
    try:
        async with get_sessionmaker()() as session:
            session.add(
                Auditoria(
                    tenant_id=tenant_id,
                    usuario_id=usuario_id,
                    email=(email or None) and email[:150],
                    accion=accion.value,
                    resultado=resultado,
                    recurso_tipo=recurso_tipo,
                    recurso_id=recurso_id,
                    ip=contexto.ip_cliente.get(),
                    request_id=contexto.request_id.get(),
                    detalle=detalle or {},
                )
            )
            await session.commit()
    except Exception:
        AUDITORIA_FALLOS.inc()
        log.exception("No se pudo registrar el evento de auditoría %s", accion.value)
