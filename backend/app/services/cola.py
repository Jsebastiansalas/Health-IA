"""Cola de procesamiento asíncrono.

Sprint 2 solo deja el documento en EN_COLA; el worker real (extracción, OCR, chunking y
vectorización) se conecta en el Sprint 3 implementando esta misma interfaz.
"""

import logging
import uuid
from typing import Protocol

log = logging.getLogger(__name__)


class ColaProcesamiento(Protocol):
    async def encolar(self, documento_id: uuid.UUID) -> None: ...


class ColaSinWorker:
    async def encolar(self, documento_id: uuid.UUID) -> None:
        log.info("Documento %s en cola (worker pendiente del Sprint 3)", documento_id)


def get_cola() -> ColaProcesamiento:
    return ColaSinWorker()
