import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.deps import CurrentUserDep, SessionDep
from app.core.enums import RolGlobal
from app.core.security import (
    TokenInvalido,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import Tenant, Usuario
from app.schemas import LoginIn, RefreshIn, RegistroTenantIn, TokensOut, UsuarioOut

router = APIRouter(prefix="/auth", tags=["auth"])

# Hash ficticio para igualar el tiempo de respuesta cuando el email no existe.
_DUMMY_HASH = hash_password("dummy-password-para-timing")


def _tokens(usuario: Usuario) -> TokensOut:
    return TokensOut(
        access_token=create_token(usuario.id, usuario.tenant_id, usuario.rol_global, "access"),
        refresh_token=create_token(usuario.id, usuario.tenant_id, usuario.rol_global, "refresh"),
    )


@router.post("/registro-tenant", response_model=TokensOut, status_code=status.HTTP_201_CREATED)
async def registrar_tenant(data: RegistroTenantIn, session: SessionDep) -> TokensOut:
    """Alta de una organización (hospital, aseguradora...) con su primer ADMIN_TENANT."""
    if not get_settings().allow_tenant_signup:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El registro de tenants está deshabilitado")

    tenant = Tenant(nombre=data.tenant_nombre, nit=data.nit, politica_borrado=data.politica_borrado)
    session.add(tenant)
    try:
        await session.flush()
        admin = Usuario(
            tenant_id=tenant.id,
            email=data.admin_email.lower(),
            password_hash=hash_password(data.admin_password),
            nombre_completo=data.admin_nombre,
            rol_global=RolGlobal.ADMIN_TENANT,
            activo=True,
        )
        session.add(admin)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "El NIT o el email ya están registrados"
        ) from exc
    return _tokens(admin)


@router.post("/login", response_model=TokensOut)
async def login(data: LoginIn, session: SessionDep) -> TokensOut:
    usuario = await session.scalar(select(Usuario).where(Usuario.email == data.email.lower()))
    valido = verify_password(data.password, usuario.password_hash if usuario else _DUMMY_HASH)
    if usuario is None or not valido or not usuario.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas")
    return _tokens(usuario)


@router.post("/refresh", response_model=TokensOut)
async def refresh(data: RefreshIn, session: SessionDep) -> TokensOut:
    try:
        payload = decode_token(data.refresh_token, "refresh")
        usuario_id = uuid.UUID(payload["sub"])
    except (TokenInvalido, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token inválido") from exc
    usuario = await session.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario inactivo o inexistente")
    # El rol se relee de la BD: un cambio de rol se refleja en el nuevo access token.
    return _tokens(usuario)


@router.get("/me", response_model=UsuarioOut)
async def me(user: CurrentUserDep, session: SessionDep) -> Usuario:
    usuario = await session.get(Usuario, user.id)
    assert usuario is not None
    return usuario
