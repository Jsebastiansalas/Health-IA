from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
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


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Sesión por petición.

    Una sesión mantiene su conexión del pool desde la primera consulta hasta que se cierra o
    confirma. Antes de cualquier espera larga (hash de contraseña, llamada a Gemini, escaneo
    antivirus) hay que soltarla con `await session.close()`: si no, N peticiones lentas
    simultáneas agotan el pool y el resto de la API se queda sin base de datos. La sesión puede
    seguir usándose después de cerrarse (toma una conexión nueva).
    """
    async with get_sessionmaker()() as session:
        yield session
