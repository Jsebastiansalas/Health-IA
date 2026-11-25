import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api import interno, proveedor_ia, sistema
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.logs import configurar_logging
from app.core.middleware import MiddlewareSolicitud
from app.ia.embeddings import get_router
from app.ia.verificacion import verificar_modelos
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


async def _verificar_en_segundo_plano() -> None:
    try:
        await verificar_modelos(get_settings(), get_router())
    except Exception:
        log.exception("No se pudo completar la verificación de modelos")


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
    verificacion = None
    if settings.verificar_modelos_al_arrancar:
        # En segundo plano: un proveedor lento no debe retrasar el arranque.
        verificacion = asyncio.create_task(_verificar_en_segundo_plano())
    tarea = None
    if settings.barrido_habilitado:
        tarea = asyncio.create_task(_bucle_barrido(settings.barrido_intervalo_s))
    log.info("Agente MedTender listo (entorno=%s)", settings.entorno)
    yield
    if verificacion:
        verificacion.cancel()
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
        title=f"{settings.app_name} - agente interno",
        version="2.0.0",
        lifespan=lifespan,
        # La documentación interactiva expone el contrato interno: solo en desarrollo.
        docs_url=None if produccion else "/docs",
        redoc_url=None,
        openapi_url=None if produccion else "/openapi.json",
    )
    # Sin CORS: nada del navegador llega aquí; solo la API Java por la red interna.
    app.add_middleware(MiddlewareSolicitud)

    app.include_router(sistema.router)
    app.include_router(interno.router)
    app.include_router(proveedor_ia.router)
    return app


app = create_app()
