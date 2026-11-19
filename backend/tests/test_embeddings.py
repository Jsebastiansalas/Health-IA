"""Proveedores de embeddings y EmbeddingRouter con HTTP simulado (respx). Sin red real."""

import json
import math

import httpx
import pytest
import respx

from app.ia import embeddings as emb
from app.ia.embeddings import (
    EmbeddingRouter,
    ErrorEmbeddings,
    GeminiEmbeddings,
    ModeloNoSoportado,
    OllamaEmbeddings,
    OpenAIEmbeddings,
    a_columna,
)

GEMINI = "https://gemini.test/v1beta"
URL_BATCH = f"{GEMINI}/models/gemini-embedding-001:batchEmbedContents"


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    async def _no_dormir(_):
        return None

    monkeypatch.setattr(emb.asyncio, "sleep", _no_dormir)


def gemini(**kw) -> GeminiEmbeddings:
    return GeminiEmbeddings("gemini-embedding-001", 4, api_key="k-prueba", base_url=GEMINI, **kw)


def respuesta_gemini(request: httpx.Request) -> httpx.Response:
    n = len(json.loads(request.content)["requests"])
    return httpx.Response(200, json={"embeddings": [{"values": [3.0, 4.0, 0.0, 0.0]}] * n})


# ---------- Gemini ----------
@respx.mock
async def test_gemini_formato_de_peticion_y_normalizacion():
    ruta = respx.post(URL_BATCH).mock(side_effect=respuesta_gemini)
    vectores = await gemini().embeber(["hola", "mundo"], "documento")

    assert vectores == [[0.6, 0.8, 0.0, 0.0]] * 2  # normalizados (norma 1)
    peticion = ruta.calls.last.request
    assert peticion.headers["x-goog-api-key"] == "k-prueba"
    assert "k-prueba" not in str(peticion.url)  # la key nunca va en la URL
    cuerpo = json.loads(peticion.content)
    assert cuerpo["requests"][0] == {
        "model": "models/gemini-embedding-001",
        "content": {"parts": [{"text": "hola"}]},
        "taskType": "RETRIEVAL_DOCUMENT",
        "outputDimensionality": 4,
    }


@respx.mock
async def test_gemini_consulta_usa_retrieval_query():
    ruta = respx.post(URL_BATCH).mock(side_effect=respuesta_gemini)
    await gemini().embeber(["¿requisitos INVIMA?"], "consulta")
    assert (
        json.loads(ruta.calls.last.request.content)["requests"][0]["taskType"] == "RETRIEVAL_QUERY"
    )


@respx.mock
async def test_gemini_parte_en_lotes():
    ruta = respx.post(URL_BATCH).mock(side_effect=respuesta_gemini)
    vectores = await gemini(lote=100).embeber([f"t{i}" for i in range(250)], "documento")
    assert len(vectores) == 250
    assert [len(json.loads(c.request.content)["requests"]) for c in ruta.calls] == [100, 100, 50]


@respx.mock
async def test_gemini_reintenta_ante_429_y_503():
    ruta = respx.post(URL_BATCH).mock(
        side_effect=[
            httpx.Response(429, headers={"retry-after": "2"}, json={"error": "cuota"}),
            httpx.Response(503, json={"error": "sobrecarga"}),
            httpx.Response(200, json={"embeddings": [{"values": [1, 0, 0, 0]}]}),
        ]
    )
    assert await gemini().embeber(["x"], "documento") == [[1.0, 0.0, 0.0, 0.0]]
    assert ruta.call_count == 3


@respx.mock
async def test_gemini_no_reintenta_errores_del_cliente():
    ruta = respx.post(URL_BATCH).mock(
        return_value=httpx.Response(400, json={"error": "API key not valid"})
    )
    with pytest.raises(ErrorEmbeddings, match="HTTP 400"):
        await gemini().embeber(["x"], "documento")
    assert ruta.call_count == 1


@respx.mock
async def test_gemini_agota_reintentos():
    respx.post(URL_BATCH).mock(return_value=httpx.Response(503))
    with pytest.raises(ErrorEmbeddings, match="HTTP 503"):
        await gemini(reintentos=3).embeber(["x"], "documento")


@respx.mock
async def test_dimension_inesperada_se_rechaza():
    respx.post(URL_BATCH).mock(
        return_value=httpx.Response(200, json={"embeddings": [{"values": [1.0, 0.0]}]})
    )
    with pytest.raises(ErrorEmbeddings, match="dimensión 2"):
        await gemini().embeber(["x"], "documento")


@respx.mock
async def test_cantidad_de_vectores_inesperada_se_rechaza():
    respx.post(URL_BATCH).mock(return_value=httpx.Response(200, json={"embeddings": []}))
    with pytest.raises(ErrorEmbeddings, match="llegaron 0"):
        await gemini().embeber(["x"], "documento")


async def test_gemini_sin_key():
    with pytest.raises(ErrorEmbeddings, match="GEMINI_API_KEY"):
        await GeminiEmbeddings("gemini-embedding-001", 4).embeber(["x"], "documento")


# ---------- OpenAI y Ollama ----------
@respx.mock
async def test_openai_respeta_el_orden_por_indice():
    respx.post("https://openai.test/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ]
            },
        )
    )
    p = OpenAIEmbeddings(
        "text-embedding-3-small", 2, api_key="k", base_url="https://openai.test/v1"
    )
    assert await p.embeber(["a", "b"], "documento") == [[1.0, 0.0], [0.0, 1.0]]


@respx.mock
async def test_ollama_bge_m3():
    ruta = respx.post("http://ollama.test:11434/api/embed").mock(
        return_value=httpx.Response(200, json={"embeddings": [[0.0, 2.0, 0.0]]})
    )
    p = OllamaEmbeddings("bge-m3", 3, base_url="http://ollama.test:11434")
    assert await p.embeber(["texto"], "documento") == [[0.0, 1.0, 0.0]]
    assert json.loads(ruta.calls.last.request.content) == {"model": "bge-m3", "input": ["texto"]}


# ---------- Router y almacenamiento ----------
async def test_router_usa_el_modelo_pedido():
    from tests.fakes import EmbeddingsFalsos

    g, o = EmbeddingsFalsos("gemini-embedding-001", 1536), EmbeddingsFalsos("bge-m3", 1024)
    router = EmbeddingRouter({"gemini-embedding-001": g, "bge-m3": o})

    assert len(await router.embeber_consulta("bge-m3", "pregunta")) == 1024
    assert o.llamadas == [("consulta", 1)] and g.llamadas == []
    assert router.modelos == {"gemini-embedding-001": 1536, "bge-m3": 1024}
    with pytest.raises(ModeloNoSoportado):
        router.proveedor("modelo-inventado")


def test_router_por_defecto_conoce_los_tres_modelos():
    from app.core.config import get_settings

    assert emb.construir_router(get_settings()).modelos == {
        "gemini-embedding-001": 1536,
        "text-embedding-3-small": 1536,
        "bge-m3": 1024,
    }


def _coseno(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True)) / (
        math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    )


def test_relleno_con_ceros_conserva_el_coseno():
    a, b = [0.3, -0.2, 0.9], [0.1, 0.5, -0.4]
    pa, pb = a_columna(a), a_columna(b)
    assert len(pa) == 1536 and pa[3:] == [0.0] * 1533
    assert math.isclose(_coseno(a, b), _coseno(pa, pb), rel_tol=1e-12)
    with pytest.raises(ErrorEmbeddings):
        a_columna([0.0] * 2000)
