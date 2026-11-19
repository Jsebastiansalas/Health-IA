"""Punto de enganche de la vectorización (Paso 7). La implementación real llega en el Sprint 4.

Contrato: recibe un documento en VECTORIZANDO con sus fragmentos guardados (embedding NULL),
rellena los embeddings y llama a purga.finalizar_indexacion para verificar y purgar.
"""

import logging
import uuid
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

log = logging.getLogger(__name__)


class Vectorizador(Protocol):
    async def vectorizar(
        self, sessionmaker: async_sessionmaker[AsyncSession], documento_id: uuid.UUID
    ) -> None: ...


class VectorizadorPendiente:
    async def vectorizar(
        self, sessionmaker: async_sessionmaker[AsyncSession], documento_id: uuid.UUID
    ) -> None:
        log.info("Documento %s listo para vectorizar (Sprint 4)", documento_id)


def get_vectorizador() -> Vectorizador:
    return VectorizadorPendiente()
