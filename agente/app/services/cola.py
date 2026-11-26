"""Cola de procesamiento asíncrono (ARQ sobre Redis)."""

import logging
import uuid
from typing import Protocol

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from app.core.config import get_settings

log = logging.getLogger(__name__)

TRABAJO_PROCESAR = "procesar_documento"
TRABAJO_REINDEXAR = "reindexar_expediente"


def id_trabajo(documento_id: uuid.UUID) -> str:
    # Id determinista: ARQ no encola dos veces el mismo documento mientras siga pendiente.
    return f"documento:{documento_id}"


class ColaProcesamiento(Protocol):
    async def encolar(self, documento_id: uuid.UUID) -> None: ...

    async def encolar_reindexacion(self, reindexacion_id: uuid.UUID) -> None: ...


class ColaSinWorker:
    """COLA_BACKEND=ninguna: el documento queda en EN_COLA."""

    async def encolar(self, documento_id: uuid.UUID) -> None:
        log.warning("Sin cola configurada: documento %s queda en EN_COLA", documento_id)

    async def encolar_reindexacion(self, reindexacion_id: uuid.UUID) -> None:
        log.warning("Sin cola configurada: reindexación %s queda PENDIENTE", reindexacion_id)


class ColaArq:
    def __init__(self, redis_url: str):
        self.redis_settings = RedisSettings.from_dsn(redis_url)
        self._pool: ArqRedis | None = None

    async def _conexion(self) -> ArqRedis:
        if self._pool is None:
            self._pool = await create_pool(self.redis_settings)
        return self._pool

    async def encolar(self, documento_id: uuid.UUID) -> None:
        pool = await self._conexion()
        await pool.enqueue_job(
            TRABAJO_PROCESAR, str(documento_id), _job_id=id_trabajo(documento_id)
        )
        log.info("Documento %s encolado", documento_id)

    async def encolar_reindexacion(self, reindexacion_id: uuid.UUID) -> None:
        pool = await self._conexion()
        await pool.enqueue_job(
            TRABAJO_REINDEXAR, str(reindexacion_id), _job_id=f"reindexacion:{reindexacion_id}"
        )

    async def cerrar(self) -> None:
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None


_cola_arq: ColaArq | None = None


def get_cola() -> ColaProcesamiento:
    global _cola_arq
    settings = get_settings()
    if settings.cola_backend == "ninguna":
        return ColaSinWorker()
    if _cola_arq is None:
        _cola_arq = ColaArq(settings.redis_url)
    return _cola_arq


async def cerrar_cola() -> None:
    if _cola_arq is not None:
        await _cola_arq.cerrar()
