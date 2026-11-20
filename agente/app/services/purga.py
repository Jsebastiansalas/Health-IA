"""Verificación de indexación, borrado físico garantizado y Acta de Purga (Paso 9).

Garantías:
1. Antes de purgar un documento indexado se verifica en PostgreSQL que
   total_chunks_esperados > 0 y COUNT(fragmentos con embedding) == total_chunks_esperados.
2. Todo error del pipeline termina en `fallar_y_purgar` (bloques finally de quien llama).
3. `barrer` (tarea periódica) recoge lo que se haya escapado: purgas diferidas vencidas,
   documentos atascados y archivos huérfanos del directorio efímero.
"""

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.enums import EstadoIndexacion as E
from app.core.enums import MotivoPurga, PoliticaBorrado
from app.models import ActaPurga, Documento, Fragmento, Tenant
from app.services import almacen_efimero
from app.services.estados import transicionar

log = logging.getLogger(__name__)


class VerificacionFallida(Exception):
    pass


async def verificar_indexacion(session: AsyncSession, documento: Documento) -> int:
    esperados = documento.total_chunks_esperados or 0
    guardados = await session.scalar(
        select(func.count())
        .select_from(Fragmento)
        .where(
            Fragmento.documento_id == documento.id,
            Fragmento.tenant_id == documento.tenant_id,
            Fragmento.embedding.is_not(None),
        )
    )
    documento.total_chunks_guardados = guardados
    if esperados <= 0:
        raise VerificacionFallida("total_chunks_esperados debe ser mayor que 0")
    if guardados != esperados:
        raise VerificacionFallida(f"Se esperaban {esperados} fragmentos y hay {guardados}")
    return guardados


def _borrar_archivos(documento_id: uuid.UUID) -> bool:
    existia_pdf = almacen_efimero.borrar(almacen_efimero.ruta_pdf(documento_id))
    existia_parcial = almacen_efimero.borrar(almacen_efimero.ruta_parcial(documento_id))
    return existia_pdf or existia_parcial


async def purgar(
    session: AsyncSession,
    documento: Documento,
    motivo: MotivoPurga,
    detalle: str | None = None,
) -> ActaPurga:
    """Borra el PDF temporal, deja el documento en un estado final y registra el acta.

    El archivo se borra antes del commit: si la BD falla, la confidencialidad ya está a salvo
    y el barrido corregirá el estado del documento.
    """
    existia = _borrar_archivos(documento.id)
    exito = motivo == MotivoPurga.INDEXADO

    if exito:
        transicionar(documento, E.INDEXADO_Y_PURGADO)
    else:
        # Un índice parcial no debe quedar consultable.
        await session.execute(delete(Fragmento).where(Fragmento.documento_id == documento.id))
        documento.total_chunks_guardados = 0
        documento.motivo_error = detalle
        transicionar(documento, E.ERROR_PURGADO)

    documento.temp_file_purged = True
    documento.purged_at = datetime.now(UTC)
    documento.purga_programada_at = None
    acta = ActaPurga(
        tenant_id=documento.tenant_id,
        documento_id=documento.id,
        sha256_original=documento.sha256_original,
        motivo=motivo,
        chunks_esperados=documento.total_chunks_esperados,
        chunks_verificados=documento.total_chunks_guardados,
        archivo_existia=existia,
        detalle=detalle,
    )
    session.add(acta)
    await session.commit()
    log.info("Purga %s documento=%s archivo_existia=%s", motivo, documento.id, existia)
    return acta


async def finalizar_indexacion(session: AsyncSession, documento: Documento) -> None:
    """Llamar al terminar la vectorización (Sprint 4). Verifica y purga según la política."""
    try:
        await verificar_indexacion(session, documento)
    except VerificacionFallida as exc:
        await purgar(session, documento, MotivoPurga.ERROR_PROCESAMIENTO, str(exc))
        raise

    politica = await session.scalar(
        select(Tenant.politica_borrado).where(Tenant.id == documento.tenant_id)
    )
    if politica == PoliticaBorrado.DIFERIDO_1H:
        transicionar(documento, E.INDEXADO_PENDIENTE_PURGA)
        documento.purga_programada_at = datetime.now(UTC) + timedelta(
            minutes=get_settings().purga_diferida_minutos
        )
        await session.commit()
    else:
        await purgar(session, documento, MotivoPurga.INDEXADO)


async def fallar_y_purgar(
    sessionmaker: async_sessionmaker[AsyncSession],
    documento_id: uuid.UUID,
    motivo: MotivoPurga,
    detalle: str,
) -> None:
    """Para bloques except/finally: usa una sesión nueva por si la anterior quedó inválida.

    Si el documento no existe o ya es final, igual se borra cualquier archivo residual.
    """
    try:
        async with sessionmaker() as session:
            documento = await session.get(Documento, documento_id, with_for_update=True)
            if documento is None or E(documento.estado_indexacion).es_final:
                _borrar_archivos(documento_id)
                return
            await purgar(session, documento, motivo, detalle)
    except Exception:
        # Último recurso: el archivo se borra aunque la BD no esté disponible.
        _borrar_archivos(documento_id)
        log.exception("No se pudo registrar la purga del documento %s", documento_id)
        raise


@dataclass
class ResumenBarrido:
    diferidas: int = 0
    timeouts: int = 0
    huerfanos: int = 0


async def barrer(
    sessionmaker: async_sessionmaker[AsyncSession], ahora: datetime | None = None
) -> ResumenBarrido:
    settings = get_settings()
    ahora = ahora or datetime.now(UTC)
    resumen = ResumenBarrido()

    async with sessionmaker() as session:
        # 1. Purgas diferidas vencidas (política DIFERIDO_1H).
        vencidas = await session.scalars(
            select(Documento)
            .where(
                Documento.estado_indexacion == E.INDEXADO_PENDIENTE_PURGA,
                Documento.purga_programada_at <= ahora,
            )
            .with_for_update(skip_locked=True)
        )
        for documento in list(vencidas):
            try:
                await verificar_indexacion(session, documento)
                await purgar(session, documento, MotivoPurga.INDEXADO)
            except VerificacionFallida as exc:
                await purgar(session, documento, MotivoPurga.ERROR_PROCESAMIENTO, str(exc))
            resumen.diferidas += 1

        # 2. Documentos atascados en un estado intermedio.
        limite = ahora - timedelta(minutes=settings.procesamiento_timeout_minutos)
        no_finales = [e for e in E if not e.es_final and e != E.INDEXADO_PENDIENTE_PURGA]
        atascados = await session.scalars(
            select(Documento)
            .where(
                Documento.estado_indexacion.in_(no_finales),
                Documento.estado_actualizado_at < limite,
            )
            .with_for_update(skip_locked=True)
        )
        for documento in list(atascados):
            estado = documento.estado_indexacion
            await purgar(
                session, documento, MotivoPurga.TIMEOUT, f"Sin avance desde el estado {estado}"
            )
            resumen.timeouts += 1

        # 3. Archivos sin documento activo. Se usa mtime: una subida en curso lo sigue
        #    actualizando, así que no se borra a mitad de transferencia.
        corte = time.time() - settings.huerfano_minutos * 60
        for ruta in almacen_efimero.directorio().iterdir():
            if not ruta.is_file() or ruta.stat().st_mtime > corte:
                continue
            documento_id = almacen_efimero.documento_id_de(ruta)
            documento = await session.get(Documento, documento_id) if documento_id else None
            if documento is not None and not E(documento.estado_indexacion).es_final:
                continue
            existia = almacen_efimero.borrar(ruta)
            session.add(
                ActaPurga(
                    tenant_id=documento.tenant_id if documento else None,
                    documento_id=documento.id if documento else None,
                    sha256_original=documento.sha256_original if documento else None,
                    motivo=MotivoPurga.HUERFANO,
                    archivo_existia=existia,
                    detalle=f"Archivo huérfano {ruta.name}",
                )
            )
            await session.commit()
            resumen.huerfanos += 1

    if resumen.diferidas or resumen.timeouts or resumen.huerfanos:
        log.info("Barrido de purga: %s", resumen)
    return resumen
