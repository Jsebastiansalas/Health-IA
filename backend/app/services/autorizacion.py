"""Autorización por expediente. Toda lectura de un expediente debe pasar por aquí.

Reglas:
- El expediente siempre se busca filtrando por tenant_id del usuario: otro tenant => 404.
- ADMIN_TENANT tiene nivel ADMIN sobre todos los expedientes de su tenant.
- Los demás necesitan una fila en expediente_permisos. Sin fila => 404 (no revela existencia);
  con fila de nivel insuficiente => 403.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.core.enums import Permiso
from app.models import Expediente, ExpedientePermiso
from app.services.auditoria import Accion, auditar


async def permiso_efectivo(
    session: AsyncSession, user: CurrentUser, expediente_id: uuid.UUID
) -> Permiso | None:
    if user.es_admin_tenant:
        return Permiso.ADMIN
    valor = await session.scalar(
        select(ExpedientePermiso.permiso).where(
            ExpedientePermiso.tenant_id == user.tenant_id,
            ExpedientePermiso.expediente_id == expediente_id,
            ExpedientePermiso.usuario_id == user.id,
        )
    )
    return Permiso(valor) if valor else None


async def obtener_expediente_autorizado(
    session: AsyncSession,
    user: CurrentUser,
    expediente_id: uuid.UUID,
    minimo: Permiso = Permiso.LECTOR,
) -> tuple[Expediente, Permiso]:
    expediente = await session.scalar(
        select(Expediente).where(
            Expediente.id == expediente_id, Expediente.tenant_id == user.tenant_id
        )
    )
    no_encontrado = HTTPException(status.HTTP_404_NOT_FOUND, "Expediente no encontrado")
    if expediente is None:
        # Inexistente o de otro tenant: la respuesta es idéntica, pero queda registrado.
        await auditar(
            Accion.ACCESO_DENEGADO,
            usuario=user,
            resultado="DENEGADO",
            recurso_tipo="expediente",
            recurso_id=expediente_id,
            detalle={"motivo": "inexistente_o_otro_tenant"},
        )
        raise no_encontrado

    permiso = await permiso_efectivo(session, user, expediente_id)
    if permiso is None:
        await auditar(
            Accion.ACCESO_DENEGADO,
            usuario=user,
            resultado="DENEGADO",
            recurso_tipo="expediente",
            recurso_id=expediente_id,
            detalle={"motivo": "sin_permiso"},
        )
        raise no_encontrado
    if permiso.nivel < minimo.nivel:
        await auditar(
            Accion.ACCESO_DENEGADO,
            usuario=user,
            resultado="DENEGADO",
            recurso_tipo="expediente",
            recurso_id=expediente_id,
            detalle={
                "motivo": "permiso_insuficiente",
                "requerido": minimo.value,
                "tiene": permiso.value,
            },
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Se requiere permiso {minimo.value}")
    return expediente, permiso
