"""Máquina de estados del pipeline de indexación."""

from datetime import UTC, datetime

from app.core.enums import EstadoIndexacion as E
from app.models import Documento

_TRANSICIONES: dict[E, set[E]] = {
    E.RECIBIDO: {E.VALIDANDO},
    E.VALIDANDO: {E.EN_COLA},
    E.EN_COLA: {E.EXTRAYENDO_OCR},
    E.EXTRAYENDO_OCR: {E.FRAGMENTANDO},
    E.FRAGMENTANDO: {E.VECTORIZANDO},
    E.VECTORIZANDO: {E.INDEXADO_PENDIENTE_PURGA, E.INDEXADO_Y_PURGADO},
    E.INDEXADO_PENDIENTE_PURGA: {E.INDEXADO_Y_PURGADO},
    E.INDEXADO_Y_PURGADO: set(),
    E.ERROR_PURGADO: set(),
}

PROGRESO: dict[E, int] = {
    E.RECIBIDO: 5,
    E.VALIDANDO: 10,
    E.EN_COLA: 15,
    E.EXTRAYENDO_OCR: 35,
    E.FRAGMENTANDO: 60,
    E.VECTORIZANDO: 80,
    E.INDEXADO_PENDIENTE_PURGA: 100,
    E.INDEXADO_Y_PURGADO: 100,
    E.ERROR_PURGADO: 100,
}


class TransicionInvalida(Exception):
    pass


def puede_transicionar(actual: E, nuevo: E) -> bool:
    if nuevo == E.ERROR_PURGADO:
        return not actual.es_final
    return nuevo in _TRANSICIONES[actual]


def transicionar(documento: Documento, nuevo: E) -> None:
    actual = E(documento.estado_indexacion)
    if not puede_transicionar(actual, nuevo):
        raise TransicionInvalida(f"{actual} -> {nuevo} no permitido")
    documento.estado_indexacion = nuevo
    documento.estado_actualizado_at = datetime.now(UTC)
