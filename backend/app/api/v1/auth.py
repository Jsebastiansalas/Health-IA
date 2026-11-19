import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core import contexto, limites
from app.core.config import get_settings
from app.core.deps import CurrentUserDep, SessionDep
from app.core.enums import RolGlobal
from app.core.security import (
    TokenInvalido,
    create_token,
    decode_token,
    hash_password,
    hash_password_async,
    verify_password_async,
)
from app.models import Tenant, Usuario
from app.schemas import LoginIn, RefreshIn, RegistroTenantIn, TokensOut, UsuarioOut
from app.services.auditoria import Accion, auditar

router = APIRouter(prefix="/auth", tags=["auth"])

# Hash ficticio para igualar el tiempo de respuesta cuando el email no existe.
_DUMMY_HASH = hash_password("dummy-password-para-timing")


def _ip() -> str:
    return contexto.ip_cliente.get() or "desconocida"


def _tokens(usuario: Usuario) -> TokensOut:
    return TokensOut(
        access_token=create_token(usuario.id, usuario.tenant_id, usuario.rol_global, "access"),
        refresh_token=create_token(usuario.id, usuario.tenant_id, usuario.rol_global, "refresh"),
    )


@router.post("/registro-tenant", response_model=TokensOut, status_code=status.HTTP_201_CREATED)
async def registrar_tenant(data: RegistroTenantIn, session: SessionDep) -> TokensOut:
    """Alta de una organización (hospital, aseguradora...) con su primer ADMIN_TENANT."""
    s = get_settings()
    if not s.allow_tenant_signup:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El registro de tenants está deshabilitado")
    await limites.exigir("registro", _ip(), s.rl_registro_ip_hora, 3600)

    # El hash (~250 ms de CPU) se calcula ANTES de tocar la base de datos y en un hilo: ni congela
    # el bucle de eventos ni retiene una conexión del pool.
    password_hash = await hash_password_async(data.admin_password)
    tenant = Tenant(nombre=data.tenant_nombre, nit=data.nit, politica_borrado=data.politica_borrado)
    session.add(tenant)
    try:
        await session.flush()
        admin = Usuario(
            tenant_id=tenant.id,
            email=data.admin_email.lower(),
            password_hash=password_hash,
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
    await auditar(
        Accion.REGISTRO_TENANT,
        tenant_id=tenant.id,
        usuario_id=admin.id,
        email=admin.email,
        recurso_tipo="tenant",
        recurso_id=tenant.id,
    )
    return _tokens(admin)


@router.post("/login", response_model=TokensOut)
async def login(data: LoginIn, session: SessionDep) -> TokensOut:
    s = get_settings()
    ip, email = _ip(), data.email.lower()
    await limites.exigir("login_ip", ip, s.rl_login_ip_min, 60)

    # Bloqueo por fallos del par (IP, correo): un atacante en otra IP no puede dejar fuera al
    # usuario legítimo, y quien adivina contraseñas desde una IP queda frenado.
    par = f"{ip}|{email}"
    estado = await limites.excedido(
        "login_fallos", par, s.rl_login_fallos_par, s.rl_login_fallos_ventana_s
    )
    if not estado.permitido:
        await auditar(Accion.LOGIN_BLOQUEADO, email=email, resultado="DENEGADO")
        raise limites.rechazar("login_fallos", estado.reintentar_en_s)

    usuario = await session.scalar(select(Usuario).where(Usuario.email == email))
    # Se devuelve la conexión al pool antes del hash: con 30 logins simultáneos, retenerla
    # durante la espera agotaba el pool y el resto de la API respondía 500. (Los atributos ya
    # cargados siguen disponibles en el objeto desligado.)
    await session.close()
    valido = await verify_password_async(
        data.password, usuario.password_hash if usuario else _DUMMY_HASH
    )
    if usuario is None or not valido or not usuario.activo:
        await limites.golpear(
            "login_fallos", par, s.rl_login_fallos_par, s.rl_login_fallos_ventana_s
        )
        await auditar(
            Accion.LOGIN_FALLIDO,
            tenant_id=usuario.tenant_id if usuario else None,
            usuario_id=usuario.id if usuario else None,
            email=email,
            resultado="DENEGADO",
            detalle={"motivo": "inactivo" if usuario and valido else "credenciales"},
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas")
    await auditar(Accion.LOGIN_OK, usuario_id=usuario.id, tenant_id=usuario.tenant_id, email=email)
    return _tokens(usuario)


@router.post("/refresh", response_model=TokensOut)
async def refresh(data: RefreshIn, session: SessionDep) -> TokensOut:
    await limites.exigir("refresh", _ip(), get_settings().rl_refresh_ip_min, 60)
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
