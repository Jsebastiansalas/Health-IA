"""API interna del agente de IA. NO es pública: solo la API Java le habla, por la red interna.

El agente no autentica usuarios ni decide permisos. Recibe, ya autorizados por Java, el tenant, el
expediente y el usuario, y los usa para acotar SIEMPRE las consultas a la base de datos (un
expediente que no pertenezca al tenant indicado se trata como inexistente). La única credencial
es el secreto compartido X-Internal-Token.
"""

import hmac
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import fijar_sistema, fijar_tenant, get_session
from app.core.enums import EstadoIndexacion as E
from app.core.metricas import CONSULTA_DURACION, CONSULTAS, LLM_RESPUESTAS
from app.ia.embeddings import EmbeddingRouter, ErrorEmbeddings, ModeloNoSoportado, get_router
from app.ia.llm import ErrorLLM, ProveedorLLM, get_llm
from app.medicamentos import busqueda as med_busqueda
from app.medicamentos import consulta as med_consulta
from app.models import Consulta, Documento, Expediente, Reindexacion
from app.rag import explicar, motor, seguridad
from app.schemas import ModeloEmbeddingOut, ReindexacionIn, ReindexacionOut
from app.services import reindexacion
from app.services.cola import ColaProcesamiento, get_cola

log = logging.getLogger(__name__)


async def exigir_token(x_internal_token: Annotated[str | None, Header()] = None) -> None:
    esperado = get_settings().internal_token
    if not esperado:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "INTERNAL_TOKEN no está configurado"
        )
    if not hmac.compare_digest((x_internal_token or "").encode(), esperado.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token interno inválido")


router = APIRouter(prefix="/internal/v1", tags=["interno"], dependencies=[Depends(exigir_token)])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
RouterDep = Annotated[EmbeddingRouter, Depends(get_router)]


async def _expediente(
    session: AsyncSession, tenant_id: uuid.UUID, expediente_id: uuid.UUID
) -> Expediente:
    """Siempre acotado al tenant: un expediente de otro tenant es 'no encontrado'."""
    fijar_tenant(session, tenant_id)  # la base solo entregará filas de este tenant
    expediente = await session.scalar(
        select(Expediente).where(Expediente.id == expediente_id, Expediente.tenant_id == tenant_id)
    )
    if expediente is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expediente no encontrado")
    return expediente


# ---------- Procesamiento de documentos ----------
@router.post("/documentos/{documento_id}/procesar", status_code=status.HTTP_202_ACCEPTED)
async def procesar_documento(
    documento_id: uuid.UUID,
    session: SessionDep,
    cola: Annotated[ColaProcesamiento, Depends(get_cola)],
) -> dict:
    """Java ya validó el PDF (firma, antivirus, estructura) y lo dejó en el directorio efímero.
    Aquí se encola su extracción, fragmentación, vectorización y purga."""
    fijar_sistema(session)  # Java no envía el tenant aquí: el documento se busca por id
    documento = await session.get(Documento, documento_id)
    if documento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    if documento.estado_indexacion != E.EN_COLA:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"El documento está en {documento.estado_indexacion}, se esperaba EN_COLA",
        )
    try:
        await cola.encolar(documento_id)
    except Exception as exc:
        log.exception("No se pudo encolar el documento %s", documento_id)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "La cola de procesamiento no está disponible"
        ) from exc
    return {"documento_id": str(documento_id), "estado": documento.estado_indexacion}


# ---------- Consultas RAG ----------
class ConsultaIn(BaseModel):
    tenant_id: uuid.UUID
    expediente_id: uuid.UUID
    usuario_id: uuid.UUID
    pregunta: str = Field(min_length=3, max_length=2000)


@router.post("/consultas")
async def consultar(
    data: ConsultaIn,
    session: SessionDep,
    emb: RouterDep,
    llm: Annotated[ProveedorLLM, Depends(get_llm)],
) -> dict:
    """Respuesta con `respuestaAnalitica`, `citas` (documento, página, SHA-256, extracto literal,
    alertas probatorias) y `alertas`."""
    expediente = await _expediente(session, data.tenant_id, data.expediente_id)
    pregunta = " ".join(data.pregunta.split())
    limite = seguridad.detectar_limite_clinico(pregunta)
    if limite:  # dosis, qué tomar o diagnóstico: respuesta fija, sin llamar a ningún modelo
        consulta_id = uuid.uuid4()
        cuerpo = seguridad.cuerpo_de_limite(limite, consulta_id, expediente.embedding_model_activo)
        session.add(
            Consulta(
                id=consulta_id,
                tenant_id=data.tenant_id,
                expediente_id=data.expediente_id,
                usuario_id=data.usuario_id,
                pregunta=pregunta,
                respuesta=cuerpo,
                sin_evidencia=True,
                modelo_embeddings=expediente.embedding_model_activo,
                modelo_llm=None,
                fragmentos_recuperados=0,
                latencia_ms=0,
            )
        )
        await session.commit()
        CONSULTAS.labels("limite_clinico").inc()
        return seguridad.con_urgencia(cuerpo, pregunta)
    try:
        r = await motor.responder(session, expediente, pregunta, emb, llm, get_settings())
    except (ErrorEmbeddings, ErrorLLM) as exc:
        CONSULTAS.labels("error_ia").inc()
        log.error("Consulta fallida expediente=%s: %s", data.expediente_id, exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "El servicio de IA no está disponible en este momento; intente de nuevo.",
        ) from exc

    CONSULTAS.labels("sin_evidencia" if r.resultado.sin_evidencia else "con_evidencia").inc()
    CONSULTA_DURACION.observe(r.latencia_ms / 1000)
    if r.modelo_llm:
        LLM_RESPUESTAS.labels(r.modelo_llm).inc()
    consulta_id = uuid.uuid4()
    cuerpo = motor.a_json(r, consulta_id)
    session.add(
        Consulta(
            id=consulta_id,
            tenant_id=data.tenant_id,
            expediente_id=data.expediente_id,
            usuario_id=data.usuario_id,
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
    # El aviso de urgencia se añade DESPUÉS de guardar: es del momento, no de la respuesta.
    return seguridad.con_urgencia(cuerpo, pregunta)


@router.get("/consultas")
async def historial(
    session: SessionDep,
    tenant_id: uuid.UUID,
    expediente_id: uuid.UUID,
    usuario_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """Consultas del usuario indicado en el expediente, la más reciente primero."""
    fijar_tenant(session, tenant_id)
    filas = await session.scalars(
        select(Consulta)
        .where(
            Consulta.tenant_id == tenant_id,
            Consulta.expediente_id == expediente_id,
            Consulta.usuario_id == usuario_id,
        )
        .order_by(Consulta.created_at.desc())
        .limit(limit)
    )
    return [
        {"pregunta": c.pregunta, "createdAt": c.created_at.isoformat(), **c.respuesta}
        for c in filas
    ]


# ---------- Explicar un documento
class ExplicacionIn(BaseModel):
    tenant_id: uuid.UUID
    expediente_id: uuid.UUID
    documento_id: uuid.UUID
    usuario_id: uuid.UUID


@router.post("/explicaciones")
async def explicar_documento(
    data: ExplicacionIn,
    session: SessionDep,
    llm: Annotated[ProveedorLLM, Depends(get_llm)],
) -> dict:
    """«Explícame este documento»: qué dice (con citas verificadas) y qué significan sus términos
    (explicación general, aparte y rotulada). Nunca diagnostica ni receta."""
    expediente = await _expediente(session, data.tenant_id, data.expediente_id)
    documento = await session.get(Documento, data.documento_id)
    if documento is None or documento.expediente_id != expediente.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    if documento.estado_indexacion not in (E.INDEXADO_Y_PURGADO, E.INDEXADO_PENDIENTE_PURGA):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El documento todavía se está procesando; intenta en un momento.",
        )
    try:
        r = await explicar.explicar(session, expediente, data.documento_id, llm, get_settings())
    except ErrorLLM as exc:
        CONSULTAS.labels("error_ia").inc()
        log.error("Explicación fallida documento=%s: %s", data.documento_id, exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "El servicio de IA no está disponible en este momento; intente de nuevo.",
        ) from exc
    CONSULTAS.labels("sin_evidencia" if r.sin_evidencia else "con_evidencia").inc()
    consulta_id = uuid.uuid4()
    cuerpo = explicar.a_json(r, consulta_id, data.documento_id, expediente.embedding_model_activo)
    session.add(
        Consulta(
            id=consulta_id,
            tenant_id=data.tenant_id,
            expediente_id=data.expediente_id,
            usuario_id=data.usuario_id,
            # Sin el nombre del archivo: puede traer el de la persona.
            pregunta=f"[Explicar documento {data.documento_id}]",
            respuesta=cuerpo,
            sin_evidencia=r.sin_evidencia,
            modelo_embeddings=expediente.embedding_model_activo,
            modelo_llm=r.modelo_llm,
            fragmentos_recuperados=r.fragmentos_analizados,
            latencia_ms=r.latencia_ms,
        )
    )
    await session.commit()
    return cuerpo


# ---------- Medicamentos (datos abiertos de INVIMA) ----------
class ConsultaMedicamentosIn(BaseModel):
    tenant_id: uuid.UUID
    usuario_id: uuid.UUID
    pregunta: str = Field(min_length=3, max_length=1000)


@router.post("/medicamentos/consultas")
async def consultar_medicamentos(
    data: ConsultaMedicamentosIn,
    session: SessionDep,
    llm: Annotated[ProveedorLLM, Depends(get_llm)],
) -> dict:
    """Pregunta sobre medicamentos de Colombia respondida solo con la base de INVIMA. No depende de
    un expediente: los datos son públicos; tenant y usuario viajan para trazabilidad."""
    pregunta = " ".join(data.pregunta.split())
    limite = seguridad.detectar_limite_clinico(pregunta, estricto=True)
    if limite:
        CONSULTAS.labels("limite_clinico").inc()
        cuerpo = seguridad.cuerpo_de_limite(limite, uuid.uuid4(), None)
        cuerpo["aviso"] = med_consulta.AVISO
        return seguridad.con_urgencia(cuerpo, pregunta)
    try:
        r = await med_consulta.responder(
            session, pregunta, llm, anonimizar=get_settings().anonimizar_antes_de_nube
        )
    except ErrorLLM as exc:
        CONSULTAS.labels("error_ia").inc()
        log.error("Consulta de medicamentos fallida: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "El servicio de IA no está disponible en este momento; intente de nuevo.",
        ) from exc
    CONSULTAS.labels("sin_evidencia" if r.sin_evidencia else "con_evidencia").inc()
    CONSULTA_DURACION.observe(r.latencia_ms / 1000)
    if r.modelo_llm:
        LLM_RESPUESTAS.labels(r.modelo_llm).inc()
    return seguridad.con_urgencia(r.cuerpo, pregunta)


@router.get("/medicamentos/fuentes")
async def fuentes_medicamentos(session: SessionDep) -> list[dict]:
    """Qué conjuntos de INVIMA están cargados, de dónde y desde cuándo."""
    return [
        {
            "fuente": c["fuente"],
            "datasetId": c["dataset_id"],
            "nombre": c["nombre"],
            "filas": c["filas"],
            "cargadoAt": c["cargado_at"].isoformat(),
        }
        for c in await med_busqueda.fuentes_cargadas(session)
    ]


# ---------- Modelos de embeddings y reindexación ----------
@router.get("/embeddings/modelos", response_model=list[ModeloEmbeddingOut])
async def listar_modelos(emb: RouterDep) -> list[ModeloEmbeddingOut]:
    return [ModeloEmbeddingOut(modelo=m, dimension=d) for m, d in emb.modelos.items()]


class ReindexacionInterna(ReindexacionIn):
    tenant_id: uuid.UUID
    expediente_id: uuid.UUID
    usuario_id: uuid.UUID


@router.post(
    "/reindexaciones", response_model=ReindexacionOut, status_code=status.HTTP_202_ACCEPTED
)
async def solicitar_reindexacion(
    data: ReindexacionInterna,
    session: SessionDep,
    emb: RouterDep,
    cola: Annotated[ColaProcesamiento, Depends(get_cola)],
) -> Reindexacion:
    """Recalcula todos los embeddings del expediente con otro modelo a partir del texto guardado
    en PostgreSQL. No necesita los PDF originales."""
    expediente = await _expediente(session, data.tenant_id, data.expediente_id)
    try:
        r = await reindexacion.solicitar(
            session, emb, expediente, data.embedding_model, data.usuario_id
        )
    except ModeloNoSoportado as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except reindexacion.ReindexacionNoPermitida as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except IntegrityError as exc:  # carrera con otra solicitud simultánea
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya hay una reindexación en curso") from exc
    await cola.encolar_reindexacion(r.id)
    return r


@router.get("/reindexaciones", response_model=list[ReindexacionOut])
async def listar_reindexaciones(
    session: SessionDep, tenant_id: uuid.UUID, expediente_id: uuid.UUID
) -> list[Reindexacion]:
    fijar_tenant(session, tenant_id)
    return list(
        await session.scalars(
            select(Reindexacion)
            .where(Reindexacion.expediente_id == expediente_id, Reindexacion.tenant_id == tenant_id)
            .order_by(Reindexacion.created_at.desc())
        )
    )
