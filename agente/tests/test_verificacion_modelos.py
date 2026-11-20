"""Verificación de modelos al arrancar (HTTP simulado, sin red) y límite de dimensión."""

import json

import httpx
import pytest
import respx

from app.core.config import Settings
from app.core.metricas import MODELO_DISPONIBLE
from app.ia import embeddings as emb
from app.ia.embeddings import EmbeddingRouter, ErrorEmbeddings, GeminiEmbeddings
from app.ia.verificacion import verificar_modelos

GEMINI = "https://gemini.test/v1beta"


def ajustes(**kw) -> Settings:
    base = {
        "gemini_api_key": "k-prueba",
        "gemini_base_url": GEMINI,
        "embedding_model_default": "gemini-embedding-001",
        "llm_model": "gemini-2.5-flash",
        "llm_modelos_respaldo": ["gemini-3.8-flash"],
    }
    return Settings(**{**base, **kw})


def router(dimension: int = 4) -> EmbeddingRouter:
    return EmbeddingRouter(
        {
            "gemini-embedding-001": GeminiEmbeddings(
                "gemini-embedding-001", dimension, api_key="k-prueba", base_url=GEMINI, reintentos=1
            )
        }
    )


def vector_de(n: int):
    def _responder(request: httpx.Request) -> httpx.Response:
        total = len(json.loads(request.content)["requests"])
        vector = {"values": [1.0] + [0.0] * (n - 1)}
        return httpx.Response(200, json={"embeddings": [vector] * total})

    return _responder


@respx.mock
async def test_todo_disponible():
    respx.post(f"{GEMINI}/models/gemini-embedding-001:batchEmbedContents").mock(
        side_effect=vector_de(4)
    )
    respx.get(f"{GEMINI}/models/gemini-2.5-flash").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{GEMINI}/models/gemini-3.8-flash").mock(return_value=httpx.Response(200, json={}))
    r = await verificar_modelos(ajustes(), router())
    assert [(x.tipo, x.modelo, x.disponible) for x in r] == [
        ("embeddings", "gemini-embedding-001", True),
        ("llm", "gemini-2.5-flash", True),
        ("llm", "gemini-3.8-flash", True),
    ]
    assert MODELO_DISPONIBLE.labels("llm", "gemini-2.5-flash")._value.get() == 1


@respx.mock
async def test_un_modelo_retirado_se_marca_no_disponible_sin_lanzar():
    respx.post(f"{GEMINI}/models/gemini-embedding-001:batchEmbedContents").mock(
        side_effect=vector_de(4)
    )
    respx.get(f"{GEMINI}/models/gemini-2.5-flash").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{GEMINI}/models/gemini-3.8-flash").mock(return_value=httpx.Response(404, json={}))
    r = await verificar_modelos(ajustes(), router())
    retirado = next(x for x in r if x.modelo == "gemini-3.8-flash")
    assert not retirado.disponible and "no reconoce" in retirado.detalle
    assert MODELO_DISPONIBLE.labels("llm", "gemini-3.8-flash")._value.get() == 0


@respx.mock
async def test_embeddings_con_dimension_distinta_a_la_declarada():
    respx.post(f"{GEMINI}/models/gemini-embedding-001:batchEmbedContents").mock(
        side_effect=vector_de(3)
    )
    respx.get(url__regex=rf"{GEMINI}/models/.*").mock(return_value=httpx.Response(200, json={}))
    r = await verificar_modelos(ajustes(), router(dimension=4))
    assert not r[0].disponible and "dimensión" in r[0].detalle


@respx.mock
async def test_proveedor_inaccesible_no_rompe_la_verificacion():
    respx.post(f"{GEMINI}/models/gemini-embedding-001:batchEmbedContents").mock(
        side_effect=httpx.ConnectError("sin red")
    )
    respx.get(url__regex=rf"{GEMINI}/models/.*").mock(side_effect=httpx.ConnectError("sin red"))
    r = await verificar_modelos(ajustes(), router())
    assert not any(x.disponible for x in r)
    assert all(x.detalle for x in r)


async def test_sin_api_key_se_informa_sin_llamar_a_la_red():
    r = await verificar_modelos(ajustes(gemini_api_key=""), router())
    llm = [x for x in r if x.tipo == "llm"]
    assert llm and all("GEMINI_API_KEY" in x.detalle for x in llm)


async def test_modelo_por_defecto_inexistente_en_el_router():
    r = await verificar_modelos(ajustes(embedding_model_default="modelo-que-no-existe"), router())
    assert not r[0].disponible and "no soportado" in r[0].detalle


def test_el_router_rechaza_dimensiones_que_no_caben_en_la_columna():
    with pytest.raises(ErrorEmbeddings, match="solo admite 1536"):
        EmbeddingRouter(
            {"modelo-grande": GeminiEmbeddings("modelo-grande", emb.EMBEDDING_DIM + 1, api_key="k")}
        )


def test_el_router_de_produccion_cabe_en_la_columna():
    emb.construir_router(Settings())  # no debe lanzar


async def test_un_fallo_inesperado_en_la_verificacion_no_tumba_el_arranque(monkeypatch):
    from app import main

    async def explota(*_):
        raise RuntimeError("fallo inesperado")

    monkeypatch.setattr(main, "verificar_modelos", explota)
    await main._verificar_en_segundo_plano()  # no debe propagar la excepción
