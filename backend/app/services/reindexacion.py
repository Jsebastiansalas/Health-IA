"""Re-vectorización de un expediente con otro modelo, sin el PDF original (HU4.4).

Usa `contenido_vectorizado`, que se conserva en PostgreSQL. Flujo:
1. PENDIENTE -> EN_PROCESO. Mientras dure, se rechazan subidas nuevas al expediente.
2. Los vectores nuevos se escriben en `fragmentos_reindex` (el índice actual sigue intacto y
   consultable con el modelo de origen).
3. Intercambio atómico en una transacción: fragmentos, documentos y expediente pasan al modelo
   nuevo a la vez. Si algo falla antes, el índice original no se toca.
"""

import logging
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.enums import EstadoIndexacion as E
from app.ia.embeddings import EmbeddingRouter, a_columna
from app.models import Documento, Expediente, Fragmento, Reindexacion

log = logging.getLogger(__name__)

ESTADOS_ACTIVOS = ("PENDIENTE", "EN_PROCESO")
_TANDA = 200
_BORRAR_PREPARADOS = text("DELETE FROM fragmentos_reindex WHERE reindexacion_id = :rid")
_ESTADOS_INDEXADOS = (E.INDEXADO_Y_PURGADO, E.INDEXADO_PENDIENTE_PURGA)


class ReindexacionNoPermitida(Exception):
    pass


async def reindexacion_activa(
    session: AsyncSession, expediente_id: uuid.UUID
) -> Reindexacion | None:
    return await session.scalar(
        select(Reindexacion).where(
            Reindexacion.expediente_id == expediente_id,
            Reindexacion.estado.in_(ESTADOS_ACTIVOS),
        )
    )


async def solicitar(
    session: AsyncSession,
    router: EmbeddingRouter,
    expediente: Expediente,
    modelo_destino: str,
    usuario_id: uuid.UUID,
) -> Reindexacion:
    router.proveedor(modelo_destino)  # ModeloNoSoportado si no existe
    if modelo_destino == expediente.embedding_model_activo:
        raise ReindexacionNoPermitida("El expediente ya usa ese modelo")
    if await reindexacion_activa(session, expediente.id):
        raise ReindexacionNoPermitida("Ya hay una reindexación en curso para este expediente")
    en_vuelo = await session.scalar(
        select(func.count())
        .select_from(Documento)
        .where(
            Documento.expediente_id == expediente.id,
            Documento.estado_indexacion.not_in(
                [E.INDEXADO_Y_PURGADO, E.INDEXADO_PENDIENTE_PURGA, E.ERROR_PURGADO]
            ),
        )
    )
    if en_vuelo:
        raise ReindexacionNoPermitida(
            f"Hay {en_vuelo} documento(s) en procesamiento; espere a que terminen"
        )
    total = await session.scalar(
        select(func.count())
        .select_from(Fragmento)
        .where(Fragmento.expediente_id == expediente.id, Fragmento.embedding.is_not(None))
    )
    r = Reindexacion(
        tenant_id=expediente.tenant_id,
        expediente_id=expediente.id,
        modelo_origen=expediente.embedding_model_activo,
        modelo_destino=modelo_destino,
        estado="PENDIENTE",
        total_fragmentos=total or 0,
        created_by=usuario_id,
    )
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return r


async def ejecutar(
    sessionmaker: async_sessionmaker[AsyncSession],
    reindexacion_id: uuid.UUID,
    router: EmbeddingRouter,
) -> None:
    t0 = time.perf_counter()
    async with sessionmaker() as session:
        r = await session.get(Reindexacion, reindexacion_id)
        if r is None or r.estado != "PENDIENTE":
            return
        r.estado = "EN_PROCESO"
        await session.commit()
        try:
            await _calcular_vectores(session, r, router)
            await _intercambiar(session, r, router)
        except Exception as exc:
            await session.rollback()
            await session.execute(_BORRAR_PREPARADOS, {"rid": reindexacion_id})
            r = await session.get(Reindexacion, reindexacion_id)
            assert r is not None
            r.estado = "ERROR"
            r.error = f"{type(exc).__name__}: {str(exc)[:300]}"
            r.finished_at = datetime.now(UTC)
            await session.commit()
            log.exception("Reindexación %s fallida; el índice original sigue intacto", r.id)
            return
    log.info(
        "Reindexación %s completada (%s -> %s) en %.1fs",
        reindexacion_id,
        r.modelo_origen,
        r.modelo_destino,
        time.perf_counter() - t0,
    )


async def _calcular_vectores(
    session: AsyncSession, r: Reindexacion, router: EmbeddingRouter
) -> None:
    ultimo_id: uuid.UUID | None = None
    while True:
        consulta = (
            select(Fragmento.id, Fragmento.contenido_vectorizado)
            .where(
                Fragmento.expediente_id == r.expediente_id,
                Fragmento.tenant_id == r.tenant_id,
                Fragmento.embedding.is_not(None),
            )
            .order_by(Fragmento.id)
            .limit(_TANDA)
        )
        if ultimo_id is not None:
            consulta = consulta.where(Fragmento.id > ultimo_id)
        tanda = (await session.execute(consulta)).all()
        if not tanda:
            return
        vectores = await router.embeber_documentos(r.modelo_destino, [t for _, t in tanda])
        await session.execute(
            text(
                "INSERT INTO fragmentos_reindex (reindexacion_id, fragmento_id, embedding) "
                "VALUES (:rid, :fid, CAST(:emb AS vector)) ON CONFLICT DO NOTHING"
            ),
            [
                {"rid": r.id, "fid": fid, "emb": str(a_columna(v))}
                for (fid, _), v in zip(tanda, vectores, strict=True)
            ],
        )
        r.fragmentos_procesados += len(tanda)
        await session.commit()
        ultimo_id = tanda[-1][0]


async def _intercambiar(session: AsyncSession, r: Reindexacion, router: EmbeddingRouter) -> None:
    preparados = await session.scalar(
        text("SELECT COUNT(*) FROM fragmentos_reindex WHERE reindexacion_id = :rid"),
        {"rid": r.id},
    )
    actuales = await session.scalar(
        select(func.count())
        .select_from(Fragmento)
        .where(Fragmento.expediente_id == r.expediente_id, Fragmento.embedding.is_not(None))
    )
    if preparados != actuales:
        raise RuntimeError(f"Vectores preparados {preparados} != fragmentos actuales {actuales}")

    expediente = await session.get(Expediente, r.expediente_id, with_for_update=True)
    assert expediente is not None
    await session.execute(
        text(
            "UPDATE fragmentos f SET embedding = s.embedding, embedding_model = :modelo "
            "FROM fragmentos_reindex s "
            "WHERE s.reindexacion_id = :rid AND s.fragmento_id = f.id"
        ),
        {"rid": r.id, "modelo": r.modelo_destino},
    )
    await session.execute(
        update(Documento)
        .where(
            Documento.expediente_id == r.expediente_id,
            Documento.estado_indexacion.in_(_ESTADOS_INDEXADOS),
        )
        .values(embedding_model=r.modelo_destino)
    )
    expediente.embedding_model_activo = r.modelo_destino
    expediente.embedding_dimension = router.proveedor(r.modelo_destino).dimension
    await session.execute(_BORRAR_PREPARADOS, {"rid": r.id})
    r.estado = "COMPLETADA"
    r.finished_at = datetime.now(UTC)
    await session.commit()  # todo o nada
