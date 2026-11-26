"""Cliente Gemini para generación: JSON estructurado y modelos de respaldo (HTTP simulado)."""

import json

import httpx
import pytest
import respx

from app.ia import embeddings
from app.ia.llm import ErrorLLM, GeminiLLM

BASE = "https://gemini.test/v1beta"


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    async def _no_dormir(_):
        return None

    monkeypatch.setattr(embeddings.asyncio, "sleep", _no_dormir)


def ok(datos: dict, pensamiento: bool = False) -> httpx.Response:
    partes = [{"text": json.dumps(datos)}]
    if pensamiento:
        partes.insert(0, {"text": "razonando...", "thought": True})
    return httpx.Response(200, json={"candidates": [{"content": {"parts": partes}}]})


def llm(*modelos: str) -> GeminiLLM:
    return GeminiLLM(list(modelos), api_key="k", base_url=BASE, reintentos=2)


@respx.mock
async def test_peticion_estructurada_y_partes_de_pensamiento():
    ruta = respx.post(f"{BASE}/models/principal:generateContent").mock(
        return_value=ok({"respuesta": "x"}, pensamiento=True)
    )
    r = await llm("principal").generar_json("sistema", "prompt", {"type": "OBJECT"})
    assert r.datos == {"respuesta": "x"} and r.modelo == "principal"
    cuerpo = json.loads(ruta.calls.last.request.content)
    assert cuerpo["systemInstruction"]["parts"][0]["text"] == "sistema"
    assert cuerpo["generationConfig"]["responseMimeType"] == "application/json"
    assert cuerpo["generationConfig"]["responseSchema"] == {"type": "OBJECT"}
    assert ruta.calls.last.request.headers["x-goog-api-key"] == "k"


@respx.mock
async def test_respaldo_si_el_principal_esta_saturado():
    principal = respx.post(f"{BASE}/models/principal:generateContent").mock(
        return_value=httpx.Response(503, json={"error": {"status": "UNAVAILABLE"}})
    )
    respaldo = respx.post(f"{BASE}/models/respaldo:generateContent").mock(return_value=ok({"a": 1}))
    r = await llm("principal", "respaldo").generar_json("s", "p", {})
    assert r.modelo == "respaldo" and r.datos == {"a": 1}
    assert principal.call_count == 2 and respaldo.call_count == 1


@respx.mock
async def test_modelo_saturado_se_salta_durante_el_enfriamiento():
    principal = respx.post(f"{BASE}/models/principal:generateContent").mock(
        return_value=httpx.Response(503)
    )
    respx.post(f"{BASE}/models/respaldo:generateContent").mock(return_value=ok({"a": 1}))
    cliente = llm("principal", "respaldo")
    await cliente.generar_json("s", "p", {})
    llamadas = principal.call_count
    # La segunda consulta va directo al respaldo: no repite los reintentos del saturado.
    r = await cliente.generar_json("s", "p", {})
    assert r.modelo == "respaldo" and principal.call_count == llamadas


@respx.mock
async def test_error_de_peticion_no_cambia_de_modelo():
    respx.post(f"{BASE}/models/principal:generateContent").mock(return_value=httpx.Response(400))
    respaldo = respx.post(f"{BASE}/models/respaldo:generateContent").mock(return_value=ok({}))
    with pytest.raises(ErrorLLM, match="HTTP 400"):
        await llm("principal", "respaldo").generar_json("s", "p", {})
    assert respaldo.call_count == 0


@respx.mock
async def test_todos_saturados():
    respx.post(url__regex=rf"{BASE}/models/.*").mock(return_value=httpx.Response(429))
    with pytest.raises(ErrorLLM, match="HTTP 429"):
        await llm("a", "b").generar_json("s", "p", {})


@respx.mock
async def test_respuesta_bloqueada_o_no_json():
    ruta = respx.post(f"{BASE}/models/m:generateContent")
    ruta.mock(return_value=httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}))
    with pytest.raises(ErrorLLM, match="SAFETY"):
        await llm("m").generar_json("s", "p", {})
    ruta.mock(
        return_value=httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "hola"}]}}]}
        )
    )
    with pytest.raises(ErrorLLM, match="no es JSON"):
        await llm("m").generar_json("s", "p", {})
