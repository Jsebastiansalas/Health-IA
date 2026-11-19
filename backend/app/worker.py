"""Worker asíncrono. Arranque: `arq app.worker.WorkerSettings`.

- procesar_documento: extracción, OCR selectivo, fragmentación (y vectorización en el Sprint 4).
- barrido_purga (cron cada 5 min): purgas diferidas, documentos atascados y archivos huérfanos.
"""

import logging
import multiprocessing
import uuid
from concurrent.futures import ProcessPoolExecutor

from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.logs import configurar_logging
from app.ia.embeddings import get_router
from app.pipeline.procesador import procesar_documento as _procesar
from app.pipeline.vectorizacion import get_vectorizador
from app.services import reindexacion
from app.services.cola import TRABAJO_PROCESAR, TRABAJO_REINDEXAR
from app.services.purga import barrer

configurar_logging(get_settings().log_json or get_settings().entorno == "produccion")
log = logging.getLogger("app.worker")


async def procesar_documento(ctx: dict, documento_id: str) -> None:
    await _procesar(
        get_sessionmaker(),
        uuid.UUID(documento_id),
        ctx["ejecutor"],
        ctx["vectorizador"],
        intento=ctx.get("job_try", 1),
    )


async def reindexar_expediente(ctx: dict, reindexacion_id: str) -> None:
    await reindexacion.ejecutar(get_sessionmaker(), uuid.UUID(reindexacion_id), get_router())


# Nombres que usa la cola para encolar.
assert procesar_documento.__qualname__ == TRABAJO_PROCESAR
assert reindexar_expediente.__qualname__ == TRABAJO_REINDEXAR


async def barrido_purga(ctx: dict) -> None:
    await barrer(get_sessionmaker())


async def startup(ctx: dict) -> None:
    # La CLI de ARQ instala su propio handler; sin esto cada línea sale dos veces.
    logging.getLogger("arq").propagate = False
    settings = get_settings()
    # "spawn": cada proceso carga su propio pdfium, sin heredar estado del padre.
    ctx["ejecutor"] = ProcessPoolExecutor(
        max_workers=settings.extraccion_procesos,
        mp_context=multiprocessing.get_context("spawn"),
    )
    ctx["vectorizador"] = get_vectorizador()
    log.info("Worker listo: %d procesos de extracción", settings.extraccion_procesos)


async def shutdown(ctx: dict) -> None:
    ctx["ejecutor"].shutdown(wait=True, cancel_futures=True)


_settings = get_settings()


class WorkerSettings:
    functions = [procesar_documento, reindexar_expediente]
    cron_jobs = [cron(barrido_purga, minute=set(range(0, 60, 5)), run_at_startup=True, unique=True)]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    max_jobs = _settings.worker_max_jobs
    job_timeout = _settings.worker_job_timeout_s
    # Un segundo intento solo cubre caídas del worker; los errores normales ya purgan.
    max_tries = 2
    keep_result = 3600
    # Latido cada 30 s: `arq --check` lo usa como sonda de salud del contenedor.
    health_check_interval = 30
