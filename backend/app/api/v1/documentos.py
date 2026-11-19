"""Ingesta efímera de PDFs (Pasos 3, 4 y 9)."""

import asyncio
import logging
import time
import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.deps import CurrentUserDep, SessionDep
from app.core.enums import EstadoExpediente, MotivoPurga, Permiso
from app.core.enums import EstadoIndexacion as E
from app.models import ActaPurga, Documento
from app.schemas import ActaPurgaOut, DocumentoDetalleOut, DocumentoMetadatos, DocumentoOut
from app.services import almacen_efimero, validacion_pdf
from app.services.antivirus import VirusScanner, get_scanner
from app.services.autorizacion import obtener_expediente_autorizado
from app.services.cola import ColaProcesamiento, get_cola
from app.services.estados import transicionar
from app.services.ingesta import validar_y_encolar
from app.services.purga import fallar_y_purgar, purgar
from app.services.subida import SubidaInvalida, recibir_pdf

log = logging.getLogger(__name__)

router = APIRouter(prefix="/expedientes/{expediente_id}/documentos", tags=["documentos"])

_OPENAPI_MULTIPART = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["archivo", "tipo_documento"],
                    "properties": {
                        "archivo": {"type": "string", "format": "binary"},
                        "tipo_documento": {
                            "type": "string",
                            "enum": [
                                "PLIEGO",
                                "ADENDA",
                                "FICHA_TECNICA",
                                "REGISTRO_SANITARIO",
                                "HISTORIA_CLINICA",
                                "PRESUPUESTO",
                            ],
                        },
                        "numero_adenda": {"type": "integer", "default": 0},
                    },
                }
            }
        },
    }
}


def _error_validacion(documento: Documento, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": documento.motivo_error,
            "documento": DocumentoOut.model_validate(documento).model_dump(mode="json"),
        },
    )


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DocumentoOut,
    openapi_extra=_OPENAPI_MULTIPART,
    responses={
        409: {"description": "PDF duplicado en el expediente o expediente no abierto"},
        413: {"description": "Archivo demasiado grande"},
        422: {"description": "Metadatos inválidos o el archivo no es un PDF"},
    },
)
async def subir_documento(
    expediente_id: uuid.UUID,
    request: Request,
    tareas: BackgroundTasks,
    user: CurrentUserDep,
    session: SessionDep,
    scanner: Annotated[VirusScanner, Depends(get_scanner)],
    cola: Annotated[ColaProcesamiento, Depends(get_cola)],
):
    """Recibe el PDF en streaming y responde 202 con estado VALIDANDO.

    El antivirus y la validación estructural (contraseña, PDF corrupto) continúan en segundo
    plano; el resultado se consulta con GET .../documentos/{id}. Un rechazo deja el documento en
    ERROR_PURGADO con su `motivo_error` y su acta de purga.
    """
    expediente, _ = await obtener_expediente_autorizado(
        session, user, expediente_id, Permiso.EDITOR
    )
    if expediente.estado != EstadoExpediente.ABIERTO:
        raise HTTPException(status.HTTP_409_CONFLICT, "El expediente no está abierto")
    # Libera la conexión mientras dura la transferencia, que puede tardar minutos.
    await session.commit()

    documento_id = uuid.uuid4()
    parcial = almacen_efimero.ruta_parcial(documento_id)
    t0 = time.perf_counter()
    try:
        recibido = await recibir_pdf(request, parcial, get_settings().max_upload_bytes)
    except SubidaInvalida as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    log.info(
        "Recepción documento=%s %.1f MB en %.1fs",
        documento_id,
        recibido.tamano / 1e6,
        time.perf_counter() - t0,
    )

    insertado = False
    try:
        try:
            meta = DocumentoMetadatos.model_validate(recibido.campos)
        except ValidationError as exc:
            errores = [
                {"loc": e["loc"], "msg": e["msg"]} for e in exc.errors(include_context=False)
            ]
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, errores) from exc

        duplicado = await session.scalar(
            select(Documento.id).where(
                Documento.tenant_id == user.tenant_id,
                Documento.expediente_id == expediente_id,
                Documento.sha256_original == recibido.sha256,
                Documento.estado_indexacion != E.ERROR_PURGADO,
            )
        )
        if duplicado:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {"msg": "Este PDF ya fue cargado en el expediente", "documento_id": str(duplicado)},
            )

        documento = Documento(
            id=documento_id,
            tenant_id=user.tenant_id,
            expediente_id=expediente_id,
            nombre_archivo_original=recibido.nombre_original,
            tipo_documento=meta.tipo_documento,
            numero_adenda=meta.numero_adenda,
            sha256_original=recibido.sha256,
            tamano_bytes=recibido.tamano,
            estado_indexacion=E.RECIBIDO,
            embedding_model=expediente.embedding_model_activo,
        )
        session.add(documento)
        await session.commit()
        insertado = True
        await session.refresh(documento)  # carga los DEFAULT del servidor
        recibido.ruta.rename(almacen_efimero.ruta_pdf(documento_id))

        transicionar(documento, E.VALIDANDO)
        await session.commit()

        # La firma binaria se comprueba aquí (instantáneo, no parsea nada) para dar respuesta
        # inmediata; antivirus y estructura van en segundo plano.
        if not validacion_pdf.tiene_firma_pdf(recibido.cabecera):
            await purgar(
                session,
                documento,
                MotivoPurga.ERROR_VALIDACION,
                "El archivo no es un PDF (firma %PDF- ausente)",
            )
            return _error_validacion(documento, status.HTTP_422_UNPROCESSABLE_CONTENT)

        tareas.add_task(validar_y_encolar, get_sessionmaker(), documento_id, scanner, cola)
        return DocumentoOut.model_validate(documento)
    except BaseException as exc:
        # Garantía de borrado: ningún camino de error deja el PDF en disco.
        if insertado:
            await asyncio.shield(
                fallar_y_purgar(
                    get_sessionmaker(),
                    documento_id,
                    MotivoPurga.ERROR_PROCESAMIENTO,
                    f"Error interno en la ingesta: {type(exc).__name__}",
                )
            )
        else:
            almacen_efimero.borrar(parcial)
        raise


@router.get("", response_model=list[DocumentoOut])
async def listar_documentos(
    expediente_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> list[Documento]:
    await obtener_expediente_autorizado(session, user, expediente_id)
    result = await session.scalars(
        select(Documento)
        .where(Documento.tenant_id == user.tenant_id, Documento.expediente_id == expediente_id)
        .order_by(Documento.uploaded_at.desc())
    )
    return list(result)


async def _documento_autorizado(
    session, user, expediente_id: uuid.UUID, documento_id: uuid.UUID, minimo: Permiso
) -> Documento:
    await obtener_expediente_autorizado(session, user, expediente_id, minimo)
    documento = await session.scalar(
        select(Documento).where(
            Documento.id == documento_id,
            Documento.expediente_id == expediente_id,
            Documento.tenant_id == user.tenant_id,
        )
    )
    if documento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    return documento


@router.get("/{documento_id}", response_model=DocumentoDetalleOut)
async def obtener_documento(
    expediente_id: uuid.UUID, documento_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> DocumentoDetalleOut:
    """Estado del pipeline (para la barra de progreso) y actas de purga."""
    documento = await _documento_autorizado(
        session, user, expediente_id, documento_id, Permiso.LECTOR
    )
    actas = await session.scalars(
        select(ActaPurga)
        .where(ActaPurga.documento_id == documento.id, ActaPurga.tenant_id == user.tenant_id)
        .order_by(ActaPurga.purged_at)
    )
    return DocumentoDetalleOut(
        **DocumentoOut.model_validate(documento).model_dump(exclude={"progreso"}),
        actas_purga=[ActaPurgaOut.model_validate(a) for a in actas],
    )


@router.delete("/{documento_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_documento(
    expediente_id: uuid.UUID, documento_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> Response:
    """Elimina el documento y sus fragmentos. El acta de purga se conserva."""
    documento = await _documento_autorizado(
        session, user, expediente_id, documento_id, Permiso.EDITOR
    )
    existia = almacen_efimero.borrar(almacen_efimero.ruta_pdf(documento.id))
    existia |= almacen_efimero.borrar(almacen_efimero.ruta_parcial(documento.id))
    session.add(
        ActaPurga(
            tenant_id=documento.tenant_id,
            documento_id=documento.id,
            sha256_original=documento.sha256_original,
            motivo=MotivoPurga.DOCUMENTO_ELIMINADO,
            chunks_esperados=documento.total_chunks_esperados,
            chunks_verificados=documento.total_chunks_guardados,
            archivo_existia=existia,
            detalle=f"Eliminado por {user.email}",
        )
    )
    await session.flush()
    await session.delete(documento)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
