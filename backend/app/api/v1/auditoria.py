"""Consulta del registro de auditoría (solo ADMIN_TENANT, siempre acotada a su tenant)."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.core.deps import AdminTenantDep, SessionDep
from app.models import Auditoria

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


class EventoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    accion: str
    resultado: str
    usuario_id: uuid.UUID | None
    email: str | None
    recurso_tipo: str | None
    recurso_id: uuid.UUID | None
    ip: str | None
    request_id: str | None
    detalle: dict


@router.get("", response_model=list[EventoOut])
async def listar_eventos(
    admin: AdminTenantDep,
    session: SessionDep,
    accion: str | None = Query(None, max_length=40),
    resultado: str | None = Query(None, pattern="^(OK|DENEGADO|ERROR)$"),
    usuario_id: uuid.UUID | None = None,
    recurso_id: uuid.UUID | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[Auditoria]:
    """Eventos del tenant, el más reciente primero. Los intentos de login contra correos que no
    pertenecen a ningún usuario no tienen tenant y no aparecen aquí (solo en los logs)."""
    consulta = select(Auditoria).where(Auditoria.tenant_id == admin.tenant_id)
    if accion:
        consulta = consulta.where(Auditoria.accion == accion)
    if resultado:
        consulta = consulta.where(Auditoria.resultado == resultado)
    if usuario_id:
        consulta = consulta.where(Auditoria.usuario_id == usuario_id)
    if recurso_id:
        consulta = consulta.where(Auditoria.recurso_id == recurso_id)
    if desde:
        consulta = consulta.where(Auditoria.created_at >= desde)
    if hasta:
        consulta = consulta.where(Auditoria.created_at <= hasta)
    filas = await session.scalars(
        consulta.order_by(Auditoria.created_at.desc()).limit(limit).offset(offset)
    )
    return list(filas)
