import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1 import auth, documentos, expedientes, tenant_usuarios
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.services.cola import cerrar_cola
from app.services.purga import barrer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
log = logging.getLogger(__name__)


async def _bucle_barrido(intervalo_s: int) -> None:
    """Equivalente al @Scheduled de barrido de huérfanos."""
    while True:
        try:
            await barrer(get_sessionmaker())
        except Exception:
            log.exception("Fallo en el barrido de purga")
        await asyncio.sleep(intervalo_s)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    tarea = None
    if settings.barrido_habilitado:
        tarea = asyncio.create_task(_bucle_barrido(settings.barrido_intervalo_s))
    yield
    if tarea:
        tarea.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarea
    await cerrar_cola()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router in (auth.router, tenant_usuarios.router, expedientes.router, documentos.router):
        app.include_router(router, prefix="/api/v1")

    @app.get("/health", tags=["sistema"])
    async def health() -> JSONResponse:
        try:
            async with get_sessionmaker()() as session:
                await session.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse({"status": "degradado", "db": "error"}, status_code=503)
        return JSONResponse({"status": "ok", "db": "ok"})

    return app


app = create_app()
