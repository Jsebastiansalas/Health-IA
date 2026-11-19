import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import contexto
from app.core.db import get_session
from app.core.enums import RolGlobal
from app.core.security import TokenInvalido, decode_token
from app.models import Usuario

_bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    tenant_id: uuid.UUID
    rol: RolGlobal
    email: str

    @property
    def es_admin_tenant(self) -> bool:
        return self.rol == RolGlobal.ADMIN_TENANT


def _no_autenticado(detalle: str = "No autenticado") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalle,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    session: SessionDep,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    if credentials is None:
        raise _no_autenticado()
    try:
        payload = decode_token(credentials.credentials, "access")
        usuario_id = uuid.UUID(payload["sub"])
        tenant_id = uuid.UUID(payload["tenant_id"])
    except (TokenInvalido, ValueError) as exc:
        raise _no_autenticado("Token inválido o expirado") from exc

    # Se consulta la BD en cada petición para que la desactivación o el cambio de rol
    # tengan efecto inmediato, aunque el token siga vigente.
    usuario = await session.scalar(
        select(Usuario).where(Usuario.id == usuario_id, Usuario.tenant_id == tenant_id)
    )
    if usuario is None or not usuario.activo:
        raise _no_autenticado("Usuario inactivo o inexistente")
    # Desde aquí, cada log de la petición lleva el usuario y el tenant.
    contexto.usuario_id.set(str(usuario.id))
    contexto.tenant_id.set(str(usuario.tenant_id))
    return CurrentUser(
        id=usuario.id,
        tenant_id=usuario.tenant_id,
        rol=RolGlobal(usuario.rol_global),
        email=usuario.email,
    )


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require_roles(*roles: RolGlobal) -> Callable:
    async def _check(user: CurrentUserDep) -> CurrentUser:
        if user.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Rol sin autorización")
        return user

    return _check


AdminTenantDep = Annotated[CurrentUser, Depends(require_roles(RolGlobal.ADMIN_TENANT))]
