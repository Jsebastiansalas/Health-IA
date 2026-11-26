"""Al terminar de indexar, el worker le pide al agente que lea el documento para la línea de tiempo.

La llamada al modelo la hace el agente (el proceso de la API), no el worker: así el tope de gasto
diario, el cortacircuitos y las métricas de IA siguen contando en un solo sitio.

Es una mejora, no un paso de la indexación: si algo falla, el documento sigue indexado y se leerá
cuando la persona abra su línea de tiempo.
"""

import logging
import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.enums import EstadoIndexacion as E
from app.models import Documento

log = logging.getLogger(__name__)

_INDEXADOS = {E.INDEXADO_PENDIENTE_PURGA, E.INDEXADO_Y_PURGADO}


async def pedir_extraccion(
    sessionmaker: async_sessionmaker[AsyncSession], documento_id: uuid.UUID | str
) -> None:
    s = get_settings()
    if not s.agente_url or not s.cronologia_al_indexar:
        return
    try:
        async with sessionmaker() as session:
            documento = await session.get(Documento, uuid.UUID(str(documento_id)))
            if documento is None or E(documento.estado_indexacion) not in _INDEXADOS:
                return
            cuerpo = {
                "tenant_id": str(documento.tenant_id),
                "expediente_id": str(documento.expediente_id),
            }
        async with httpx.AsyncClient(timeout=s.agente_timeout_s) as cliente:
            respuesta = await cliente.post(
                f"{s.agente_url.rstrip('/')}/internal/v1/documentos/{documento_id}/linea",
                headers={"X-Internal-Token": s.internal_token},
                json=cuerpo,
            )
            respuesta.raise_for_status()
    except Exception as exc:
        # Solo el tipo del fallo: el mensaje podría traer texto de la respuesta.
        log.warning(
            "No se pudo leer el documento %s para la línea de tiempo (%s); "
            "se leerá al abrir la línea de tiempo",
            documento_id,
            type(exc).__name__,
        )
