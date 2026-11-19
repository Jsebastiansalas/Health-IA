import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, literal, select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.deps import CurrentUserDep, SessionDep
from app.core.enums import ROLES_CREADORES, Permiso
from app.ia.embeddings import get_router
from app.models import Expediente, ExpedientePermiso, Usuario
from app.schemas import (
    ExpedienteCreate,
    ExpedienteOut,
    ExpedienteUpdate,
    PermisoIn,
    PermisoOut,
)
from app.services.autorizacion import obtener_expediente_autorizado

router = APIRouter(prefix="/expedientes", tags=["expedientes"])


def _out(expediente: Expediente, permiso: Permiso | None) -> ExpedienteOut:
    out = ExpedienteOut.model_validate(expediente)
    out.mi_permiso = permiso
    return out


@router.get("", response_model=list[ExpedienteOut])
async def listar_expedientes(
    user: CurrentUserDep,
    session: SessionDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[ExpedienteOut]:
    if user.es_admin_tenant:
        stmt = select(Expediente, literal(Permiso.ADMIN.value)).where(
            Expediente.tenant_id == user.tenant_id
        )
    else:
        stmt = (
            select(Expediente, ExpedientePermiso.permiso)
            .join(ExpedientePermiso, ExpedientePermiso.expediente_id == Expediente.id)
            .where(
                Expediente.tenant_id == user.tenant_id,
                ExpedientePermiso.tenant_id == user.tenant_id,
                ExpedientePermiso.usuario_id == user.id,
            )
        )
    stmt = stmt.order_by(Expediente.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).all()
    return [_out(exp, Permiso(perm)) for exp, perm in rows]


@router.post("", response_model=ExpedienteOut, status_code=status.HTTP_201_CREATED)
async def crear_expediente(
    data: ExpedienteCreate, user: CurrentUserDep, session: SessionDep
) -> ExpedienteOut:
    if user.rol not in ROLES_CREADORES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Tu rol no puede crear expedientes")
    modelo = get_settings().embedding_model_default
    expediente = Expediente(
        tenant_id=user.tenant_id,
        created_by=user.id,
        embedding_model_activo=modelo,
        embedding_dimension=get_router().proveedor(modelo).dimension,
        **data.model_dump(),
    )
    session.add(expediente)
    try:
        await session.flush()
        # El creador queda como ADMIN del expediente.
        session.add(
            ExpedientePermiso(
                tenant_id=user.tenant_id,
                expediente_id=expediente.id,
                usuario_id=user.id,
                permiso=Permiso.ADMIN,
            )
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ya existe un expediente con ese código"
        ) from exc
    await session.refresh(expediente)
    return _out(expediente, Permiso.ADMIN)


@router.get("/{expediente_id}", response_model=ExpedienteOut)
async def obtener_expediente(
    expediente_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> ExpedienteOut:
    expediente, permiso = await obtener_expediente_autorizado(session, user, expediente_id)
    return _out(expediente, permiso)


@router.patch("/{expediente_id}", response_model=ExpedienteOut)
async def actualizar_expediente(
    expediente_id: uuid.UUID, data: ExpedienteUpdate, user: CurrentUserDep, session: SessionDep
) -> ExpedienteOut:
    expediente, permiso = await obtener_expediente_autorizado(
        session, user, expediente_id, Permiso.EDITOR
    )
    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(expediente, campo, valor)
    await session.commit()
    return _out(expediente, permiso)


@router.delete("/{expediente_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_expediente(
    expediente_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> Response:
    expediente, _ = await obtener_expediente_autorizado(session, user, expediente_id, Permiso.ADMIN)
    await session.delete(expediente)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Permisos por expediente ----------
@router.get("/{expediente_id}/permisos", response_model=list[PermisoOut])
async def listar_permisos(
    expediente_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> list[PermisoOut]:
    await obtener_expediente_autorizado(session, user, expediente_id, Permiso.ADMIN)
    rows = (
        await session.execute(
            select(Usuario.id, Usuario.email, Usuario.nombre_completo, ExpedientePermiso.permiso)
            .join(ExpedientePermiso, ExpedientePermiso.usuario_id == Usuario.id)
            .where(
                ExpedientePermiso.expediente_id == expediente_id,
                ExpedientePermiso.tenant_id == user.tenant_id,
            )
            .order_by(Usuario.email)
        )
    ).all()
    return [
        PermisoOut(usuario_id=uid, email=email, nombre_completo=nombre, permiso=Permiso(perm))
        for uid, email, nombre, perm in rows
    ]


@router.put("/{expediente_id}/permisos/{usuario_id}", response_model=PermisoOut)
async def asignar_permiso(
    expediente_id: uuid.UUID,
    usuario_id: uuid.UUID,
    data: PermisoIn,
    user: CurrentUserDep,
    session: SessionDep,
) -> PermisoOut:
    await obtener_expediente_autorizado(session, user, expediente_id, Permiso.ADMIN)
    destino = await session.scalar(
        select(Usuario).where(Usuario.id == usuario_id, Usuario.tenant_id == user.tenant_id)
    )
    if destino is None:
        # Un usuario de otro tenant se trata como inexistente.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")

    existente = await session.scalar(
        select(ExpedientePermiso).where(
            ExpedientePermiso.expediente_id == expediente_id,
            ExpedientePermiso.usuario_id == usuario_id,
        )
    )
    if existente is None:
        session.add(
            ExpedientePermiso(
                tenant_id=user.tenant_id,
                expediente_id=expediente_id,
                usuario_id=usuario_id,
                permiso=data.permiso,
            )
        )
    else:
        if existente.permiso == Permiso.ADMIN and data.permiso != Permiso.ADMIN:
            await _asegurar_otro_admin(session, expediente_id, usuario_id)
        existente.permiso = data.permiso
    await session.commit()
    return PermisoOut(
        usuario_id=destino.id,
        email=destino.email,
        nombre_completo=destino.nombre_completo,
        permiso=data.permiso,
    )


@router.delete("/{expediente_id}/permisos/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revocar_permiso(
    expediente_id: uuid.UUID, usuario_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> Response:
    await obtener_expediente_autorizado(session, user, expediente_id, Permiso.ADMIN)
    existente = await session.scalar(
        select(ExpedientePermiso).where(
            ExpedientePermiso.expediente_id == expediente_id,
            ExpedientePermiso.usuario_id == usuario_id,
            ExpedientePermiso.tenant_id == user.tenant_id,
        )
    )
    if existente is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permiso no encontrado")
    if existente.permiso == Permiso.ADMIN:
        await _asegurar_otro_admin(session, expediente_id, usuario_id)
    await session.delete(existente)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _asegurar_otro_admin(session, expediente_id: uuid.UUID, usuario_id: uuid.UUID) -> None:
    """Impide dejar un expediente sin ningún permiso ADMIN explícito."""
    otros = await session.scalar(
        select(func.count())
        .select_from(ExpedientePermiso)
        .where(
            ExpedientePermiso.expediente_id == expediente_id,
            ExpedientePermiso.permiso == Permiso.ADMIN,
            ExpedientePermiso.usuario_id != usuario_id,
        )
    )
    if not otros:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "El expediente debe conservar al menos un ADMIN"
        )
