"""Verificación de los modelos de IA al arrancar.

Un nombre de modelo mal escrito, retirado por el proveedor o sin API key solo se descubre hoy
cuando alguien sube un PDF o hace una pregunta, y el fallo llega al usuario. Aquí se comprueba al
iniciar y el resultado queda en el log y en la métrica `medtender_modelo_disponible`, para alertar
antes. Nunca impide arrancar: un proveedor caído no debe tumbar el resto del servicio.

- Embeddings: el modelo por defecto de los expedientes nuevos se prueba con una llamada real
  (cuesta un vector) y se comprueba que la dimensión coincida con la declarada.
- LLM: el principal y los de respaldo se consultan por su ficha (`GET models/{id}`), sin generar
  texto ni gastar tokens.
"""

import logging
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.core.metricas import MODELO_DISPONIBLE
from app.ia.embeddings import EmbeddingRouter, ErrorEmbeddings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResultadoModelo:
    tipo: str  # "embeddings" | "llm"
    modelo: str
    disponible: bool
    detalle: str


async def _verificar_embeddings(s: Settings, router: EmbeddingRouter) -> ResultadoModelo:
    modelo = s.embedding_model_default
    try:
        proveedor = router.proveedor(modelo)
        vectores = await proveedor.embeber(["verificación de arranque"], "consulta")
    except ErrorEmbeddings as exc:
        return ResultadoModelo("embeddings", modelo, False, str(exc))
    if len(vectores) != 1 or len(vectores[0]) != proveedor.dimension:
        return ResultadoModelo("embeddings", modelo, False, "dimensión distinta de la declarada")
    return ResultadoModelo("embeddings", modelo, True, f"dimensión {proveedor.dimension}")


async def _verificar_llm(s: Settings, modelo: str, cliente: httpx.AsyncClient) -> ResultadoModelo:
    if not s.gemini_api_key:
        return ResultadoModelo("llm", modelo, False, "GEMINI_API_KEY no configurada")
    try:
        r = await cliente.get(
            f"{s.gemini_base_url}/models/{modelo}", headers={"x-goog-api-key": s.gemini_api_key}
        )
    except httpx.TransportError as exc:
        return ResultadoModelo("llm", modelo, False, f"proveedor inaccesible: {type(exc).__name__}")
    if r.status_code == 200:
        return ResultadoModelo("llm", modelo, True, "ficha del modelo encontrada")
    if r.status_code == 404:
        return ResultadoModelo("llm", modelo, False, "el proveedor no reconoce este modelo")
    return ResultadoModelo("llm", modelo, False, f"HTTP {r.status_code}")


async def verificar_modelos(s: Settings, router: EmbeddingRouter) -> list[ResultadoModelo]:
    resultados = [await _verificar_embeddings(s, router)]
    modelos = [s.llm_model, *[m for m in s.llm_modelos_respaldo if m != s.llm_model]]
    async with httpx.AsyncClient(timeout=10.0) as cliente:
        resultados += [await _verificar_llm(s, m, cliente) for m in modelos]

    for r in resultados:
        MODELO_DISPONIBLE.labels(r.tipo, r.modelo).set(1 if r.disponible else 0)
        if r.disponible:
            log.info("Modelo %s %s: disponible (%s)", r.tipo, r.modelo, r.detalle)
        else:
            log.error("Modelo %s %s NO disponible: %s", r.tipo, r.modelo, r.detalle)
    return resultados
