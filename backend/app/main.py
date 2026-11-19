import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import sistema
from app.api.v1 import (
    auditoria,
    auth,
    consultas,
    documentos,
    expedientes,
    reindexacion,
    tenant_usuarios,
)
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.logs import configurar_logging
from app.core.middleware import MiddlewareSolicitud
from app.services.cola import cerrar_cola
from app.services.purga import barrer

log = logging.getLogger(__name__)


async def _bucle_barrido(intervalo_s: int) -> None:
    """Equivalente al @Scheduled de barrido de huérfanos."""
    while True:
        try:
            await barrer(get_sessionmaker())
        except Exception:
            log.exception("Fallo en el barrido de purga")
        await asyncio.sleep(intervalo_s)


def validar_configuracion() -> None:
    """En producción, una configuración insegura impide arrancar."""
    s = get_settings()
    fatales, avisos = s.problemas_produccion()
    if s.entorno != "produccion":
        return
    for a in avisos:
        log.warning("Configuración: %s", a)
    if fatales:
        for f in fatales:
            log.critical("Configuración insegura: %s", f)
        raise RuntimeError("Configuración insegura para producción: " + "; ".join(fatales))


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    validar_configuracion()
    tarea = None
    if settings.barrido_habilitado:
        tarea = asyncio.create_task(_bucle_barrido(settings.barrido_intervalo_s))
    log.info("MedTender API lista (entorno=%s)", settings.entorno)
    yield
    if tarea:
        tarea.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarea
    await cerrar_cola()


def create_app() -> FastAPI:
    settings = get_settings()
    produccion = settings.entorno == "produccion"
    configurar_logging(settings.log_json or produccion)
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
        # La documentación interactiva expone el contrato completo: solo en desarrollo.
        docs_url=None if produccion else "/docs",
        redoc_url=None,
        openapi_url=None if produccion else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    # El último en añadirse es el más externo: contexto, límite general y métricas cubren todo.
    app.add_middleware(MiddlewareSolicitud)

    app.include_router(sistema.router)
    for router in (
        auth.router,
        tenant_usuarios.router,
        expedientes.router,
        documentos.router,
        reindexacion.router,
        consultas.router,
        auditoria.router,
    ):
        app.include_router(router, prefix="/api/v1")

    return app


app = create_app()
