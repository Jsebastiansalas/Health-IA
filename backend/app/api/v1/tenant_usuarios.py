"""Administración del tenant y sus usuarios (solo ADMIN_TENANT)."""

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.deps import AdminTenantDep, SessionDep
from app.core.enums import RolGlobal
from app.core.security import hash_password
from app.models import Tenant, Usuario
from app.schemas import TenantOut, TenantUpdate, UsuarioCreate, UsuarioOut, UsuarioUpdate

router = APIRouter(tags=["tenant"])


@router.get("/tenant", response_model=TenantOut)
async def obtener_tenant(admin: AdminTenantDep, session: SessionDep) -> Tenant:
    tenant = await session.get(Tenant, admin.tenant_id)
    assert tenant is not None
    return tenant


@router.patch("/tenant", response_model=TenantOut)
async def actualizar_tenant(
    data: TenantUpdate, admin: AdminTenantDep, session: SessionDep
) -> Tenant:
    tenant = await session.get(Tenant, admin.tenant_id)
    assert tenant is not None
    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(tenant, campo, valor)
    await session.commit()
    return tenant


@router.get("/usuarios", response_model=list[UsuarioOut])
async def listar_usuarios(
    admin: AdminTenantDep,
    session: SessionDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[Usuario]:
    result = await session.scalars(
        select(Usuario)
        .where(Usuario.tenant_id == admin.tenant_id)
        .order_by(Usuario.created_at)
        .limit(limit)
        .offset(offset)
    )
    return list(result)


@router.post("/usuarios", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
async def crear_usuario(data: UsuarioCreate, admin: AdminTenantDep, session: SessionDep) -> Usuario:
    usuario = Usuario(
        tenant_id=admin.tenant_id,
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        nombre_completo=data.nombre_completo,
        rol_global=data.rol_global,
        activo=True,
    )
    session.add(usuario)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "El email ya está registrado") from exc
    await session.refresh(usuario)
    return usuario


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioOut)
async def actualizar_usuario(
    usuario_id: uuid.UUID, data: UsuarioUpdate, admin: AdminTenantDep, session: SessionDep
) -> Usuario:
    usuario = await session.scalar(
        select(Usuario).where(Usuario.id == usuario_id, Usuario.tenant_id == admin.tenant_id)
    )
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")

    cambios = data.model_dump(exclude_unset=True)
    pierde_admin = cambios.get("activo") is False or (
        "rol_global" in cambios and cambios["rol_global"] != RolGlobal.ADMIN_TENANT
    )
    if usuario.id == admin.id and pierde_admin:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "No puedes desactivarte ni quitarte el rol de administrador"
        )
    for campo, valor in cambios.items():
        setattr(usuario, campo, valor)
    await session.commit()
    return usuario
