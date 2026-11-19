"""Proveedores de embeddings y EmbeddingRouter (Pasos 7 y 11).

Regla de oro: la pregunta se vectoriza con **exactamente el mismo modelo** que el índice del
expediente consultado (`expedientes.embedding_model_activo`). El router es el único punto que
traduce un nombre de modelo a un proveedor.

Todos los vectores se guardan en `fragmentos.embedding vector(1536)`. Un modelo de menor
dimensión (p. ej. bge-m3, 1024) se rellena con ceros: la similitud coseno entre dos vectores
rellenados con ceros es idéntica a la de los originales, así que el índice HNSW sigue sirviendo.
"""

import asyncio
import logging
import math
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

from app.core.config import Settings, get_settings
from app.models import EMBEDDING_DIM

log = logging.getLogger(__name__)

Tarea = Literal["documento", "consulta"]


class ErrorEmbeddings(Exception):
    pass


class ModeloNoSoportado(ErrorEmbeddings):
    pass


class ProveedorEmbeddings(Protocol):
    modelo: str
    dimension: int

    async def embeber(self, textos: list[str], tarea: Tarea) -> list[list[float]]: ...


def normalizar(vector: list[float]) -> list[float]:
    norma = math.sqrt(sum(x * x for x in vector))
    return [x / norma for x in vector] if norma else vector


def a_columna(vector: list[float]) -> list[float]:
    """Ajusta el vector a la columna vector(1536) rellenando con ceros."""
    if len(vector) > EMBEDDING_DIM:
        raise ErrorEmbeddings(f"Dimensión {len(vector)} supera la columna ({EMBEDDING_DIM})")
    return vector + [0.0] * (EMBEDDING_DIM - len(vector))


# ---------- HTTP con reintentos ----------
_REINTENTABLES = {408, 429, 500, 502, 503, 504}


async def _post(
    cliente: httpx.AsyncClient, url: str, json: dict, headers: dict, reintentos: int
) -> dict:
    espera = 1.0
    for intento in range(1, reintentos + 1):
        try:
            r = await cliente.post(url, json=json, headers=headers)
        except httpx.TransportError as exc:
            if intento == reintentos:
                raise ErrorEmbeddings(f"Proveedor inaccesible: {exc}") from exc
        else:
            if r.status_code == 200:
                return r.json()
            if r.status_code not in _REINTENTABLES or intento == reintentos:
                # El cuerpo de error nunca incluye la API key; se recorta por si es largo.
                raise ErrorEmbeddings(f"HTTP {r.status_code}: {r.text[:300]}")
            retry_after = r.headers.get("retry-after", "")
            if retry_after.isdigit():
                espera = max(espera, float(retry_after))
        log.warning("Embeddings: intento %d fallido, reintento en %.0fs", intento, espera)
        await asyncio.sleep(espera)
        espera = min(espera * 2, 60)
    raise ErrorEmbeddings("Reintentos agotados")  # pragma: no cover


@dataclass
class _Base:
    modelo: str
    dimension: int
    lote: int = 100
    reintentos: int = 6
    timeout_s: float = 60.0

    async def embeber(self, textos: list[str], tarea: Tarea) -> list[list[float]]:
        vectores: list[list[float]] = []
        async with httpx.AsyncClient(timeout=self.timeout_s) as cliente:
            for i in range(0, len(textos), self.lote):
                lote = textos[i : i + self.lote]
                nuevos = await self._lote(cliente, lote, tarea)
                if len(nuevos) != len(lote):
                    raise ErrorEmbeddings(
                        f"Se pidieron {len(lote)} vectores y llegaron {len(nuevos)}"
                    )
                for v in nuevos:
                    if len(v) != self.dimension:
                        raise ErrorEmbeddings(
                            f"{self.modelo} devolvió dimensión {len(v)}, "
                            f"se esperaba {self.dimension}"
                        )
                vectores += nuevos
        return vectores

    async def _lote(
        self, cliente: httpx.AsyncClient, textos: list[str], tarea: Tarea
    ) -> list[list[float]]:
        raise NotImplementedError


# ---------- Gemini (AI Studio) ----------
@dataclass
class GeminiEmbeddings(_Base):
    api_key: str = ""
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    async def _lote(self, cliente, textos, tarea):
        if not self.api_key:
            raise ErrorEmbeddings("GEMINI_API_KEY no configurada")
        tipo = "RETRIEVAL_DOCUMENT" if tarea == "documento" else "RETRIEVAL_QUERY"
        cuerpo = {
            "requests": [
                {
                    "model": f"models/{self.modelo}",
                    "content": {"parts": [{"text": t}]},
                    "taskType": tipo,
                    "outputDimensionality": self.dimension,
                }
                for t in textos
            ]
        }
        datos = await _post(
            cliente,
            f"{self.base_url}/models/{self.modelo}:batchEmbedContents",
            cuerpo,
            {"x-goog-api-key": self.api_key},
            self.reintentos,
        )
        # Con dimensión reducida (< 3072) Google recomienda normalizar los vectores.
        return [normalizar(e["values"]) for e in datos.get("embeddings", [])]


# ---------- OpenAI (proveedor del documento original) ----------
@dataclass
class OpenAIEmbeddings(_Base):
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"

    async def _lote(self, cliente, textos, tarea):
        if not self.api_key:
            raise ErrorEmbeddings("OPENAI_API_KEY no configurada")
        datos = await _post(
            cliente,
            f"{self.base_url}/embeddings",
            {"model": self.modelo, "input": textos},
            {"Authorization": f"Bearer {self.api_key}"},
            self.reintentos,
        )
        ordenados = sorted(datos.get("data", []), key=lambda d: d["index"])
        return [d["embedding"] for d in ordenados]


# ---------- Ollama (proveedor local, Fase 2) ----------
@dataclass
class OllamaEmbeddings(_Base):
    base_url: str = "http://localhost:11434"
    timeout_s: float = 300.0  # en CPU, un lote puede tardar

    async def _lote(self, cliente, textos, tarea):
        datos = await _post(
            cliente,
            f"{self.base_url}/api/embed",
            {"model": self.modelo, "input": textos},
            {},
            self.reintentos,
        )
        return [normalizar(v) for v in datos.get("embeddings", [])]


# ---------- Router ----------
class EmbeddingRouter:
    def __init__(self, proveedores: dict[str, ProveedorEmbeddings]):
        self._proveedores = proveedores

    @property
    def modelos(self) -> dict[str, int]:
        return {nombre: p.dimension for nombre, p in self._proveedores.items()}

    def proveedor(self, modelo: str) -> ProveedorEmbeddings:
        try:
            return self._proveedores[modelo]
        except KeyError:
            raise ModeloNoSoportado(f"Modelo de embeddings no soportado: {modelo}") from None

    async def embeber_documentos(self, modelo: str, textos: list[str]) -> list[list[float]]:
        return await self.proveedor(modelo).embeber(textos, "documento")

    async def embeber_consulta(self, modelo: str, texto: str) -> list[float]:
        """Paso 11: `modelo` debe ser el embedding_model_activo del expediente consultado."""
        return (await self.proveedor(modelo).embeber([texto], "consulta"))[0]


def construir_router(s: Settings) -> EmbeddingRouter:
    comun = {"lote": s.embedding_lote, "reintentos": s.embedding_reintentos}
    return EmbeddingRouter(
        {
            "gemini-embedding-001": GeminiEmbeddings(
                "gemini-embedding-001",
                1536,
                api_key=s.gemini_api_key,
                base_url=s.gemini_base_url,
                **comun,
            ),
            "text-embedding-3-small": OpenAIEmbeddings(
                "text-embedding-3-small",
                1536,
                api_key=s.openai_api_key,
                base_url=s.openai_base_url,
                **comun,
            ),
            "bge-m3": OllamaEmbeddings("bge-m3", 1024, base_url=s.ollama_url, **comun),
        }
    )


_router: EmbeddingRouter | None = None


def get_router() -> EmbeddingRouter:
    global _router
    if _router is None:
        _router = construir_router(get_settings())
    return _router
