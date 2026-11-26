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
from app.core.db import fijar_sistema, fijar_tenant, get_session, get_sessionmaker
from app.core.enums import EstadoIndexacion as E
from app.core.metricas import CONSULTA_DURACION, CONSULTAS, LLM_RESPUESTAS
from app.ia.embeddings import EmbeddingRouter, ErrorEmbeddings, ModeloNoSoportado, get_router
from app.ia.llm import ErrorLLM, ProveedorLLM, get_llm
from app.medicamentos import busqueda as med_busqueda
from app.medicamentos import consulta as med_consulta
from app.models import Consulta, Documento, Expediente, Reindexacion, Tenant
from app.rag import (
    cronologia,
    cruce,
    explicar,
    garantias,
    motor,
    preparacion,
    recordatorios,
    seguridad,
)
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
    cuerpo = garantias.sin_posologia_inventada(motor.a_json(r, consulta_id))
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


# ---------- Cruce de medicamentos con fichas
class CruceIn(BaseModel):
    tenant_id: uuid.UUID
    expediente_id: uuid.UUID
    usuario_id: uuid.UUID


@router.post("/cruces")
async def cruzar_medicamentos(
    data: CruceIn,
    session: SessionDep,
    llm: Annotated[ProveedorLLM, Depends(get_llm)],
) -> dict:
    """Medicamentos de los documentos del expediente y lo que advierten sus fichas técnicas frente
    a los diagnósticos y alergias del propio documento, con cita a ambos lados. Nunca elige,
    recomienda ni dosifica."""
    expediente = await _expediente(session, data.tenant_id, data.expediente_id)
    try:
        r = await cruce.cruzar(session, expediente, llm, get_settings())
    except ErrorLLM as exc:
        CONSULTAS.labels("error_ia").inc()
        log.error("Cruce fallido expediente=%s: %s", data.expediente_id, exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "El servicio de IA no está disponible en este momento; intente de nuevo.",
        ) from exc
    CONSULTAS.labels("sin_evidencia" if r.sin_evidencia else "con_evidencia").inc()
    consulta_id = uuid.uuid4()
    cuerpo = garantias.sin_posologia_inventada(
        cruce.a_json(r, consulta_id, expediente.embedding_model_activo)
    )
    async with get_sessionmaker()() as guardar:
        fijar_tenant(guardar, data.tenant_id)
        guardar.add(
            Consulta(
                id=consulta_id,
                tenant_id=data.tenant_id,
                expediente_id=data.expediente_id,
                usuario_id=data.usuario_id,
                pregunta="[Cruce de medicamentos]",
                respuesta=cuerpo,
                sin_evidencia=r.sin_evidencia,
                modelo_embeddings=expediente.embedding_model_activo,
                modelo_llm=r.modelo_llm,
                fragmentos_recuperados=r.fragmentos,
                latencia_ms=r.latencia_ms,
            )
        )
        await guardar.commit()
    return cuerpo


# ---------- Línea de tiempo y evolución de resultados
class CronologiaIn(BaseModel):
    tenant_id: uuid.UUID
    expediente_id: uuid.UUID
    usuario_id: uuid.UUID
    # Rehacerla aunque los documentos no hayan cambiado (p. ej. tras mejorar el agente).
    rehacer: bool = False


async def _cronologia_de(
    session: AsyncSession,
    expediente: Expediente,
    usuario_id: uuid.UUID,
    rehacer: bool,
    llm: ProveedorLLM,
) -> dict:
    """La línea de tiempo del expediente: la guardada si los documentos no cambiaron (sin llamar al
    modelo) o una nueva, que queda en el historial. Puede lanzar ErrorLLM."""
    huella = await cronologia.huella_actual(session, expediente)
    if not rehacer:
        # La pregunta está cifrada, así que se busca por la huella y se confirma al leer.
        candidatas = await session.scalars(
            select(Consulta)
            .where(
                Consulta.tenant_id == expediente.tenant_id,
                Consulta.expediente_id == expediente.id,
                Consulta.respuesta["huella"].astext == huella,
            )
            .order_by(Consulta.created_at.desc())
            .limit(5)
        )
        guardada = next(
            (c for c in candidatas if c.pregunta == cronologia.PREGUNTA_HISTORIAL), None
        )
        if guardada is not None:
            return {
                **guardada.respuesta,
                "guardada": True,
                "generadaAt": guardada.created_at.isoformat(),
            }
    r = await cronologia.armar(session, expediente, llm, get_settings(), huella, rehacer)
    CONSULTAS.labels("sin_evidencia" if r.sin_evidencia else "con_evidencia").inc()
    consulta_id = uuid.uuid4()
    cuerpo = cronologia.a_json(r, consulta_id, expediente.embedding_model_activo)
    generada = await _guardar_en_historial(
        expediente, usuario_id, cronologia.PREGUNTA_HISTORIAL, cuerpo, r.sin_evidencia,
        r.modelo_llm, r.fragmentos, r.latencia_ms,
    )  # fmt: skip
    return {**cuerpo, "guardada": False, "generadaAt": generada}


async def _guardar_en_historial(
    expediente: Expediente,
    usuario_id: uuid.UUID,
    pregunta: str,
    cuerpo: dict,
    sin_evidencia: bool,
    modelo_llm: str | None,
    fragmentos: int,
    latencia_ms: int,
) -> str:
    """Guarda la respuesta en `consultas` con una sesión propia (la de la petición pudo cerrarse
    mientras respondía el modelo) y devuelve la fecha en que quedó guardada."""
    async with get_sessionmaker()() as guardar:
        fijar_tenant(guardar, expediente.tenant_id)
        fila = Consulta(
            id=uuid.UUID(cuerpo["consultaId"]),
            tenant_id=expediente.tenant_id,
            expediente_id=expediente.id,
            usuario_id=usuario_id,
            pregunta=pregunta,
            respuesta=cuerpo,
            sin_evidencia=sin_evidencia,
            modelo_embeddings=expediente.embedding_model_activo,
            modelo_llm=modelo_llm,
            fragmentos_recuperados=fragmentos,
            latencia_ms=latencia_ms,
        )
        guardar.add(fila)
        await guardar.commit()
        await guardar.refresh(fila)
        return fila.created_at.isoformat()


def _sin_ia(exc: Exception, que: str, expediente_id: uuid.UUID) -> HTTPException:
    CONSULTAS.labels("error_ia").inc()
    log.error("%s fallida expediente=%s: %s", que, expediente_id, exc)
    return HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "El servicio de IA no está disponible en este momento; intente de nuevo.",
    )


@router.post("/cronologias")
async def armar_cronologia(
    data: CronologiaIn,
    session: SessionDep,
    llm: Annotated[ProveedorLLM, Depends(get_llm)],
) -> dict:
    """Eventos con fecha y valores de laboratorio de los documentos del expediente, ordenados y
    con cita en cada dato. No interpreta resultados. Si los documentos no cambiaron desde la
    última vez, se devuelve la guardada sin llamar al modelo."""
    expediente = await _expediente(session, data.tenant_id, data.expediente_id)
    try:
        return await _cronologia_de(session, expediente, data.usuario_id, data.rehacer, llm)
    except ErrorLLM as exc:
        raise _sin_ia(exc, "Línea de tiempo", data.expediente_id) from exc


class LineaDocumentoIn(BaseModel):
    tenant_id: uuid.UUID
    expediente_id: uuid.UUID


@router.post("/documentos/{documento_id}/linea")
async def leer_documento_para_la_linea(
    documento_id: uuid.UUID,
    data: LineaDocumentoIn,
    session: SessionDep,
    llm: Annotated[ProveedorLLM, Depends(get_llm)],
) -> dict:
    """La pide el worker al terminar de indexar: así abrir la línea de tiempo no tiene que llamar al
    modelo. Solo cuentas personales, y nunca los prospectos."""
    expediente = await _expediente(session, data.tenant_id, data.expediente_id)
    documento = await session.get(Documento, documento_id)
    if documento is None or documento.expediente_id != expediente.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    s = get_settings()
    tenant = await session.get(Tenant, expediente.tenant_id)
    if not s.cronologia_al_indexar or tenant is None or tenant.tipo != "PERSONAL":
        return {"estado": "omitida"}
    try:
        estado = await cronologia.extraer_de_documento(session, expediente, documento_id, llm, s)
        return {"estado": estado}
    except ErrorLLM as exc:
        raise _sin_ia(exc, "Lectura para la línea de tiempo", expediente.id) from exc


class ExpedienteIn(BaseModel):
    tenant_id: uuid.UUID
    expediente_id: uuid.UUID
    usuario_id: uuid.UUID


# ---------- Recordatorios de controles
@router.post("/recordatorios/propuestas")
async def proponer_recordatorios(
    data: ExpedienteIn,
    session: SessionDep,
    llm: Annotated[ProveedorLLM, Depends(get_llm)],
) -> dict:
    """Los controles que indican los documentos, con una fecha propuesta (calculada por código) y su
    cita. Solo propuestas: Java las guarda y la persona confirma cada una. Reutiliza la línea de
    tiempo guardada, así que normalmente no llama al modelo."""
    expediente = await _expediente(session, data.tenant_id, data.expediente_id)
    try:
        linea = await _cronologia_de(session, expediente, data.usuario_id, False, llm)
    except ErrorLLM as exc:
        raise _sin_ia(exc, "Propuesta de recordatorios", data.expediente_id) from exc
    return {
        "propuestas": recordatorios.propuestas(linea),
        "lineaGuardada": bool(linea.get("guardada")),
    }


# ---------- Preparar mi cita
class PreparacionIn(BaseModel):
    tenant_id: uuid.UUID
    expediente_id: uuid.UUID
    usuario_id: uuid.UUID


@router.post("/preparaciones")
async def preparar_cita(
    data: PreparacionIn,
    session: SessionDep,
    llm: Annotated[ProveedorLLM, Depends(get_llm)],
) -> dict:
    """Resumen de una página para llevar a la cita: lo reciente, lo que cambió, los medicamentos,
    diagnósticos y alergias que escriben los documentos (con cita) y preguntas sugeridas para el
    médico. No diagnostica, no receta y no interpreta resultados."""
    expediente = await _expediente(session, data.tenant_id, data.expediente_id)
    try:
        linea = await _cronologia_de(session, expediente, data.usuario_id, False, llm)
        r = await preparacion.preparar(expediente, llm, get_settings(), linea)
    except ErrorLLM as exc:
        raise _sin_ia(exc, "Preparación de cita", data.expediente_id) from exc
    CONSULTAS.labels("sin_evidencia" if r["sinEvidencia"] else "con_evidencia").inc()
    generada = await _guardar_en_historial(
        expediente, data.usuario_id, preparacion.PREGUNTA_HISTORIAL, r, r["sinEvidencia"],
        r.get("modeloLlm"), r.get("fragmentosRecuperados", 0), r.get("latenciaMs", 0),
    )  # fmt: skip
    return {**r, "generadaAt": generada}


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
    return seguridad.con_urgencia(garantias.sin_posologia_inventada(r.cuerpo), pregunta)


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
