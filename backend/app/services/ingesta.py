"""Validación asíncrona tras la recepción (antivirus + estructura) y paso a la cola.

Se ejecuta fuera de la petición HTTP porque escanear un PDF de cientos de MB con ClamAV puede
tardar más de un minuto. El cliente sigue el progreso con GET .../documentos/{id}.

Ninguna conexión de base de datos se mantiene durante el escaneo: se abre una sesión corta para
comprobar el estado, otra para registrar el resultado.
"""

import asyncio
import logging
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.enums import EstadoIndexacion as E
from app.core.enums import MotivoPurga
from app.models import Documento
from app.services import almacen_efimero, validacion_pdf
from app.services.antivirus import AntivirusNoDisponible, VirusScanner
from app.services.cola import ColaProcesamiento
from app.services.estados import transicionar
from app.services.purga import fallar_y_purgar, purgar

log = logging.getLogger(__name__)


async def _motivo_rechazo(
    documento_id: uuid.UUID, scanner: VirusScanner
) -> tuple[str | None, int | None]:
    """(motivo de rechazo, páginas). Antivirus primero: un archivo malicioso no debe llegar al
    parser de PDF. No toca la base de datos."""
    ruta = almacen_efimero.ruta_pdf(documento_id)
    t0 = time.perf_counter()
    try:
        resultado = await scanner.escanear(ruta)
    except AntivirusNoDisponible as exc:
        log.error("Antivirus no disponible documento=%s: %s", documento_id, exc)
        return "El antivirus no está disponible; vuelva a cargar el PDF más tarde", None
    t_av = time.perf_counter() - t0
    if not resultado.limpio:
        log.warning("Virus detectado documento=%s firma=%s", documento_id, resultado.firma)
        return f"Archivo rechazado por el antivirus: {resultado.firma}", None

    t0 = time.perf_counter()
    try:
        info = await asyncio.to_thread(validacion_pdf.inspeccionar, ruta)
    except validacion_pdf.PdfInvalido as exc:
        return str(exc), None
    log.info(
        "Validación documento=%s antivirus=%.1fs estructura=%.1fs páginas=%d",
        documento_id,
        t_av,
        time.perf_counter() - t0,
        info.total_paginas,
    )
    return None, info.total_paginas


async def validar_y_encolar(
    sessionmaker: async_sessionmaker[AsyncSession],
    documento_id: uuid.UUID,
    scanner: VirusScanner,
    cola: ColaProcesamiento,
) -> None:
    try:
        async with sessionmaker() as session:
            documento = await session.get(Documento, documento_id)
            if documento is None or documento.estado_indexacion != E.VALIDANDO:
                return

        motivo, paginas = await _motivo_rechazo(documento_id, scanner)

        async with sessionmaker() as session:
            documento = await session.get(Documento, documento_id)
            if documento is None or documento.estado_indexacion != E.VALIDANDO:
                # Eliminado o expirado mientras se escaneaba: no debe quedar el archivo.
                almacen_efimero.borrar(almacen_efimero.ruta_pdf(documento_id))
                return
            if motivo:
                await purgar(session, documento, MotivoPurga.ERROR_VALIDACION, motivo)
                return
            documento.total_paginas = paginas
            transicionar(documento, E.EN_COLA)
            await session.commit()
        await cola.encolar(documento_id)
    except BaseException as exc:
        # Garantía de borrado también para la parte asíncrona.
        await asyncio.shield(
            fallar_y_purgar(
                sessionmaker,
                documento_id,
                MotivoPurga.ERROR_PROCESAMIENTO,
                f"Error interno en la validación: {type(exc).__name__}",
            )
        )
        if not isinstance(exc, Exception):
            raise
        log.exception("Error validando documento %s", documento_id)
