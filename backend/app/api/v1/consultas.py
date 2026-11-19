"""Consola RAG: preguntas sobre un expediente con respuesta fundamentada y citas (Pasos 10-14)."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import CurrentUserDep, SessionDep
from app.ia.embeddings import EmbeddingRouter, ErrorEmbeddings, get_router
from app.ia.llm import ErrorLLM, ProveedorLLM, get_llm
from app.models import Consulta
from app.rag import motor
from app.services.autorizacion import obtener_expediente_autorizado

log = logging.getLogger(__name__)
router = APIRouter(prefix="/expedientes/{expediente_id}/consultas", tags=["consultas"])


class PreguntaIn(BaseModel):
    pregunta: str = Field(min_length=3, max_length=2000)


@router.post("", status_code=status.HTTP_200_OK)
async def consultar(
    expediente_id: uuid.UUID,
    data: PreguntaIn,
    user: CurrentUserDep,
    session: SessionDep,
    emb: Annotated[EmbeddingRouter, Depends(get_router)],
    llm: Annotated[ProveedorLLM, Depends(get_llm)],
) -> dict:
    """Respuesta con `respuestaAnalitica`, `citas` (documento, página, SHA-256, extracto literal,
    alertas probatorias) y `alertas`. Requiere permiso LECTOR sobre el expediente."""
    expediente, _ = await obtener_expediente_autorizado(session, user, expediente_id)
    pregunta = " ".join(data.pregunta.split())
    try:
        r = await motor.responder(session, expediente, pregunta, emb, llm, get_settings())
    except (ErrorEmbeddings, ErrorLLM) as exc:
        log.error("Consulta fallida expediente=%s: %s", expediente_id, exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "El servicio de IA no está disponible en este momento; intente de nuevo.",
        ) from exc

    consulta_id = uuid.uuid4()
    cuerpo = motor.a_json(r, consulta_id)
    session.add(
        Consulta(
            id=consulta_id,
            tenant_id=user.tenant_id,
            expediente_id=expediente_id,
            usuario_id=user.id,
            pregunta=pregunta,
            respuesta=cuerpo,
            sin_evidencia=r.resultado.sin_evidencia,
            modelo_embeddings=r.modelo_embeddings,
            modelo_llm=r.modelo_llm,
            fragmentos_recuperados=r.fragmentos_recuperados,
            latencia_ms=r.latencia_ms,
        )
    )
    await session.commit()
    return cuerpo


@router.get("")
async def historial(
    expediente_id: uuid.UUID,
    user: CurrentUserDep,
    session: SessionDep,
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """Consultas propias del usuario en el expediente, la más reciente primero."""
    await obtener_expediente_autorizado(session, user, expediente_id)
    filas = await session.scalars(
        select(Consulta)
        .where(
            Consulta.tenant_id == user.tenant_id,
            Consulta.expediente_id == expediente_id,
            Consulta.usuario_id == user.id,
        )
        .order_by(Consulta.created_at.desc())
        .limit(limit)
    )
    return [
        {"pregunta": c.pregunta, "createdAt": c.created_at.isoformat(), **c.respuesta}
        for c in filas
    ]
