import uuid
from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    if settings.db_null_pool:
        return create_async_engine(settings.database_url, poolclass=NullPool)
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        # Fallar rápido: esperar 30 s por una conexión deja la API "colgada" sin avisar.
        pool_timeout=settings.db_pool_timeout_s,
        pool_recycle=1800,
    )


# ---------- Aislamiento por tenant (Row-Level Security, migración V8) ----------
# PostgreSQL decide qué filas ve cada transacción según `app.tenant_id` y `app.sistema`. Aquí se
# declaran al abrir CADA transacción (SET LOCAL: no sobreviven al commit ni al pool).
#
# - Sesiones de PETICIÓN (get_session): nacen sin contexto, así que no ven ninguna fila hasta que
#   el endpoint llama a `fijar_tenant`. Olvidarlo falla cerrado, no abierto.
# - Sesiones de SISTEMA (get_sessionmaker): worker, barrido de purga, CLI y métricas. Procesan
#   documentos de cualquier tenant, por eso ven todos.
@event.listens_for(Session, "after_begin")
def _declarar_contexto(session: Session, transaction, connection) -> None:
    sistema = bool(session.info.get("sistema"))
    tenant = session.info.get("tenant_id") or ""
    connection.execute(
        text(
            "SELECT set_config('app.tenant_id', :tenant, true), "
            "set_config('app.sistema', :sis, true)"
        ),
        {"tenant": tenant, "sis": "on" if sistema else "off"},
    )


def fijar_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """La sesión de la petición actúa en nombre de este tenant (y solo de él)."""
    session.sync_session.info["tenant_id"] = str(tenant_id)
    session.sync_session.info["sistema"] = False


def fijar_sistema(session: AsyncSession) -> None:
    """La sesión de la petición actúa como proceso del sistema (cruza tenants)."""
    session.sync_session.info["sistema"] = True


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Sesiones del SISTEMA (worker, barrido, CLI, métricas): ven todos los tenants."""
    return async_sessionmaker(get_engine(), expire_on_commit=False, info={"sistema": True})


@lru_cache
def _sessionmaker_peticion() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Sesión por petición.

    Una sesión mantiene su conexión del pool desde la primera consulta hasta que se cierra o
    confirma. Antes de cualquier espera larga (hash de contraseña, llamada a Gemini, escaneo
    antivirus) hay que soltarla con `await session.close()`: si no, N peticiones lentas
    simultáneas agotan el pool y el resto de la API se queda sin base de datos. La sesión puede
    seguir usándose después de cerrarse (toma una conexión nueva).
    """
    async with _sessionmaker_peticion()() as session:
        yield session
