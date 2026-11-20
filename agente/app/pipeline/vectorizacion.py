"""Vectorización (Pasos 7, 8 y 9).

Recibe un documento en VECTORIZANDO con sus fragmentos guardados (embedding NULL):
1. Vectoriza `contenido_vectorizado` (texto + cabecera contextual) por lotes con el modelo
   activo del expediente, elegido por el EmbeddingRouter.
2. Guarda cada lote en cuanto llega y actualiza `total_chunks_guardados` (barra de progreso).
3. Llama a `finalizar_indexacion`: verificación COUNT == esperados y purga según la política.
"""

import logging
import time
import uuid
from typing import Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.enums import EstadoIndexacion as E
from app.ia.embeddings import EmbeddingRouter, a_columna, get_router
from app.models import Documento, Expediente, Fragmento
from app.services.purga import finalizar_indexacion

log = logging.getLogger(__name__)

# Fragmentos que se leen y guardan por vuelta (el proveedor los subdivide en sus lotes).
_TANDA = 200


class Vectorizador(Protocol):
    async def vectorizar(
        self, sessionmaker: async_sessionmaker[AsyncSession], documento_id: uuid.UUID
    ) -> None: ...


class VectorizadorEmbeddings:
    def __init__(self, router: EmbeddingRouter):
        self.router = router

    async def vectorizar(
        self, sessionmaker: async_sessionmaker[AsyncSession], documento_id: uuid.UUID
    ) -> None:
        t0 = time.perf_counter()
        async with sessionmaker() as session:
            documento = await session.get(Documento, documento_id)
            if documento is None or documento.estado_indexacion != E.VECTORIZANDO:
                return
            expediente = await session.get(Expediente, documento.expediente_id)
            assert expediente is not None
            # El índice del expediente manda: si cambió de modelo mientras el documento
            # esperaba en cola, se vectoriza con el modelo vigente.
            modelo = expediente.embedding_model_activo
            documento.embedding_model = modelo
            self.router.proveedor(modelo)  # falla pronto si el modelo no está soportado

            while True:
                tanda = (
                    await session.execute(
                        select(Fragmento.id, Fragmento.contenido_vectorizado)
                        .where(
                            Fragmento.documento_id == documento.id,
                            Fragmento.tenant_id == documento.tenant_id,
                            Fragmento.embedding.is_(None),
                        )
                        .order_by(Fragmento.orden)
                        .limit(_TANDA)
                    )
                ).all()
                if not tanda:
                    break
                vectores = await self.router.embeber_documentos(modelo, [t for _, t in tanda])
                await session.execute(
                    update(Fragmento),
                    [
                        {"id": fid, "embedding": a_columna(v), "embedding_model": modelo}
                        for (fid, _), v in zip(tanda, vectores, strict=True)
                    ],
                )
                documento.total_chunks_guardados = (documento.total_chunks_guardados or 0) + len(
                    tanda
                )
                await session.commit()

            await finalizar_indexacion(session, documento)
        log.info(
            "Vectorización documento=%s modelo=%s fragmentos=%s en %.1fs",
            documento_id,
            modelo,
            documento.total_chunks_guardados,
            time.perf_counter() - t0,
        )


def get_vectorizador() -> Vectorizador:
    return VectorizadorEmbeddings(get_router())
