"""Contratos de la API interna. Los contratos públicos (los que ve el frontend) viven en Java."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ReindexacionIn(BaseModel):
    embedding_model: str = Field(min_length=1, max_length=80)


class ReindexacionOut(ORMModel):
    id: uuid.UUID
    expediente_id: uuid.UUID
    modelo_origen: str
    modelo_destino: str
    estado: str
    total_fragmentos: int
    fragmentos_procesados: int
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class ModeloEmbeddingOut(BaseModel):
    modelo: str
    dimension: int
