"""Re-vectorización de un expediente sin volver a subir los PDF (HU4.4)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.deps import CurrentUserDep, SessionDep
from app.core.enums import Permiso
from app.ia.embeddings import EmbeddingRouter, ModeloNoSoportado, get_router
from app.models import Reindexacion
from app.schemas import ModeloEmbeddingOut, ReindexacionIn, ReindexacionOut
from app.services import reindexacion
from app.services.autorizacion import obtener_expediente_autorizado
from app.services.cola import ColaProcesamiento, get_cola

router = APIRouter(tags=["embeddings"])

RouterDep = Annotated[EmbeddingRouter, Depends(get_router)]


@router.get("/embeddings/modelos", response_model=list[ModeloEmbeddingOut])
async def listar_modelos(user: CurrentUserDep, emb: RouterDep) -> list[ModeloEmbeddingOut]:
    return [ModeloEmbeddingOut(modelo=m, dimension=d) for m, d in emb.modelos.items()]


@router.post(
    "/expedientes/{expediente_id}/reindexaciones",
    response_model=ReindexacionOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def solicitar_reindexacion(
    expediente_id: uuid.UUID,
    data: ReindexacionIn,
    user: CurrentUserDep,
    session: SessionDep,
    emb: RouterDep,
    cola: Annotated[ColaProcesamiento, Depends(get_cola)],
) -> Reindexacion:
    """Recalcula todos los embeddings del expediente con otro modelo a partir del texto
    guardado en PostgreSQL. No necesita los PDF originales."""
    expediente, _ = await obtener_expediente_autorizado(session, user, expediente_id, Permiso.ADMIN)
    try:
        r = await reindexacion.solicitar(session, emb, expediente, data.embedding_model, user.id)
    except ModeloNoSoportado as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except reindexacion.ReindexacionNoPermitida as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except IntegrityError as exc:  # carrera con otra solicitud simultánea
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya hay una reindexación en curso") from exc
    await cola.encolar_reindexacion(r.id)
    return r


@router.get("/expedientes/{expediente_id}/reindexaciones", response_model=list[ReindexacionOut])
async def listar_reindexaciones(
    expediente_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> list[Reindexacion]:
    await obtener_expediente_autorizado(session, user, expediente_id)
    return list(
        await session.scalars(
            select(Reindexacion)
            .where(
                Reindexacion.expediente_id == expediente_id,
                Reindexacion.tenant_id == user.tenant_id,
            )
            .order_by(Reindexacion.created_at.desc())
        )
    )
