"""Trabajo asíncrono por documento: EN_COLA -> EXTRAYENDO_OCR -> FRAGMENTANDO -> VECTORIZANDO.

Garantías:
- Idempotente: si el documento no está en EN_COLA, no hace nada (salvo reintento tras caída).
- Reintento tras caída del worker: si ARQ reintenta un trabajo que quedó a medias
  (EXTRAYENDO_OCR / FRAGMENTANDO), se borran los fragmentos parciales y se reprocesa.
- Cualquier error termina en fallar_y_purgar: el PDF temporal nunca queda en disco.
"""

import asyncio
import logging
import time
import uuid
from concurrent.futures import Executor

from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.enums import EstadoIndexacion as E
from app.core.enums import MotivoPurga
from app.models import Documento, Expediente, Fragmento
from app.pipeline.extraccion import extraer_documento
from app.pipeline.fragmentacion import Fragmentador, cabecera_contextual
from app.pipeline.modelos import (
    EXTRACTOR_VERSION,
    ConfigExtraccion,
    ConfigFragmentacion,
    FragmentoGenerado,
)
from app.pipeline.vectorizacion import Vectorizador
from app.services import almacen_efimero
from app.services.estados import transicionar
from app.services.purga import fallar_y_purgar

log = logging.getLogger(__name__)


class DocumentoSinTexto(Exception):
    pass


class ArchivoTemporalAusente(Exception):
    pass


def config_extraccion(s: Settings) -> ConfigExtraccion:
    return ConfigExtraccion(
        umbral_texto_nativo=s.umbral_texto_nativo,
        ocr_dpi=s.ocr_dpi,
        ocr_idioma=s.ocr_idioma,
        imagen_relevante_min_area=s.imagen_relevante_min_area,
        imagen_escaneo_min_area=s.imagen_escaneo_min_area,
        imagen_sello_max_area=s.imagen_sello_max_area,
    )


def config_fragmentacion(s: Settings) -> ConfigFragmentacion:
    return ConfigFragmentacion(
        min_tokens=s.chunk_min_tokens,
        max_tokens=s.chunk_max_tokens,
        overlap_ratio=s.chunk_overlap_ratio,
    )


def _filas(
    documento: Documento, expediente: Expediente, fragmentos: list[FragmentoGenerado]
) -> list[dict]:
    return [
        {
            "tenant_id": documento.tenant_id,
            "expediente_id": documento.expediente_id,
            "documento_id": documento.id,
            "orden": f.orden,
            "pagina_inicio": f.pagina_inicio,
            "pagina_fin": f.pagina_fin,
            "seccion": f.seccion,
            "contenido_texto": f.texto,
            "contenido_vectorizado": cabecera_contextual(
                expediente.codigo_expediente,
                documento.nombre_archivo_original,
                documento.tipo_documento,
                f,
            ),
            "token_count": f.token_count,
            "embedding_model": documento.embedding_model,
            "embedding": None,
            "metadata_jsonb": {
                **f.metadata,
                "tipo_documento": documento.tipo_documento,
                "numero_adenda": documento.numero_adenda or 0,
            },
        }
        for f in fragmentos
    ]


async def _preparar(session: AsyncSession, documento: Documento, intento: int) -> bool:
    """Devuelve True si el documento debe procesarse en este intento."""
    estado = E(documento.estado_indexacion)
    if estado == E.EN_COLA:
        return True
    if intento > 1 and estado in (E.EXTRAYENDO_OCR, E.FRAGMENTANDO):
        log.warning("Reintento %d de %s desde %s: se reprocesa", intento, documento.id, estado)
        await session.execute(delete(Fragmento).where(Fragmento.documento_id == documento.id))
        transicionar(documento, E.EN_COLA)
        return True
    log.info("Documento %s en %s: nada que procesar", documento.id, estado)
    return False


async def procesar_documento(
    sessionmaker: async_sessionmaker[AsyncSession],
    documento_id: uuid.UUID,
    ejecutor: Executor | None,
    vectorizador: Vectorizador,
    intento: int = 1,
) -> None:
    settings = get_settings()
    try:
        async with sessionmaker() as session:
            documento = await session.get(Documento, documento_id)
            if documento is None:
                almacen_efimero.borrar(almacen_efimero.ruta_pdf(documento_id))
                return
            if not await _preparar(session, documento, intento):
                return
            expediente = await session.get(Expediente, documento.expediente_id)
            assert expediente is not None
            ruta = almacen_efimero.ruta_pdf(documento.id)
            if not ruta.exists():
                raise ArchivoTemporalAusente("El PDF temporal ya no está en el servidor")

            # --- Paso 5: extracción + OCR selectivo (en un proceso aparte) ---
            transicionar(documento, E.EXTRAYENDO_OCR)
            await session.commit()
            t0 = time.perf_counter()
            resultado = await asyncio.get_running_loop().run_in_executor(
                ejecutor, extraer_documento, str(ruta), config_extraccion(settings)
            )
            ocr = sum(1 for p in resultado.paginas if p.metodo == "OCR")
            log.info(
                "Extracción documento=%s páginas=%d ocr=%d en %.1fs",
                documento.id,
                len(resultado.paginas),
                ocr,
                time.perf_counter() - t0,
            )
            documento.total_paginas = len(resultado.paginas)
            documento.extractor_version = EXTRACTOR_VERSION
            if resultado.ocr_version:
                documento.ocr_version = resultado.ocr_version

            # --- Paso 6: fragmentación ---
            transicionar(documento, E.FRAGMENTANDO)
            await session.commit()
            fragmentador = Fragmentador(config_fragmentacion(settings))
            fragmentos = await asyncio.to_thread(fragmentador.fragmentar, resultado.paginas)
            if not fragmentos:
                raise DocumentoSinTexto("No se pudo extraer texto de ninguna página")

            await session.execute(insert(Fragmento), _filas(documento, expediente, fragmentos))
            documento.total_chunks_esperados = len(fragmentos)
            documento.total_chunks_guardados = 0
            transicionar(documento, E.VECTORIZANDO)
            await session.commit()
            log.info("Fragmentación documento=%s fragmentos=%d", documento.id, len(fragmentos))

        # --- Paso 7 en adelante (Sprint 4) ---
        await vectorizador.vectorizar(sessionmaker, documento_id)
    except BaseException as exc:
        detalle = f"{type(exc).__name__}: {str(exc)[:300]}" if str(exc) else type(exc).__name__
        await asyncio.shield(
            fallar_y_purgar(sessionmaker, documento_id, MotivoPurga.ERROR_PROCESAMIENTO, detalle)
        )
        if not isinstance(exc, Exception):
            raise
        log.exception("Error procesando documento %s", documento_id)
