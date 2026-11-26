"""Vertex con modelos, regiones y precios vigentes (documentación de Google, 25-nov-2026):

- gemini-2.5-flash se retiraba de Agent Platform (Vertex) el 20-oct-2026.
- gemini-3.8-flash se ofrece en «global» y en las multirregiones us y eu, no en us-central1.
- Las multirregiones usan el host aiplatform.{us|eu}.rep.googleapis.com.
- El ejemplo REST documentado de gemini-embedding-001 es en us-central1.
"""

import json

import httpx
import pytest
import respx

from app.core.config import Settings
from app.ia import embeddings
from app.ia.costo import PRECIOS_REFERENCIA, ControlDeCosto, Uso
from app.ia.embeddings import construir_router
from app.ia.google_auth import vertex_url
from app.ia.llm import ErrorLLM, GeminiLLM, LLMConRespaldo, construir_llm

BASE = "https://gemini.test/v1beta"


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    async def _no_dormir(_):
        return None

    monkeypatch.setattr(embeddings.asyncio, "sleep", _no_dormir)
    for nombre in (
        "LLM_MODEL",
        "LLM_MODELOS_RESPALDO",
        "VERTEX_REGION",
        "VERTEX_REGION_EMBEDDINGS",
    ):
        monkeypatch.delenv(nombre, raising=False)


def ajustes(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


def ok(datos: dict) -> httpx.Response:
    return httpx.Response(
        200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(datos)}]}}]}
    )


# ---------- modelos y regiones por defecto ----------
def test_con_vertex_los_modelos_por_defecto_son_vigentes():
    s = ajustes(ia_proveedor="vertex", vertex_proyecto="p")
    assert s.llm_model == "gemini-3.8-flash"
    assert s.llm_modelos_respaldo == ["gemini-3.5-flash"]
    assert s.vertex_region == "global"
    assert s.vertex_region_embeddings == "us-central1"


def test_la_api_gratuita_conserva_sus_modelos():
    """El retiro es de Vertex: la beta con AI Studio no cambia."""
    s = ajustes(ia_proveedor="gemini_api")
    assert s.llm_model == "gemini-2.5-flash"
    assert s.llm_modelos_respaldo == ["gemini-3.8-flash"]


def test_lo_que_se_configura_a_mano_se_respeta():
    s = ajustes(ia_proveedor="vertex", llm_model="otro-modelo", llm_modelos_respaldo=[])
    assert s.llm_model == "otro-modelo" and s.llm_modelos_respaldo == []


def test_el_modelo_y_los_embeddings_van_cada_uno_a_su_region():
    s = ajustes(ia_proveedor="vertex", vertex_proyecto="p")
    llm = construir_llm(s).proveedores[0][1]
    emb = construir_router(s).proveedor("gemini-embedding-001")
    assert llm.region == "global" and emb.region == "us-central1"


def test_produccion_avisa_si_se_pide_un_modelo_retirado_de_vertex():
    _, avisos = ajustes(
        ia_proveedor="vertex", vertex_proyecto="p", llm_model="gemini-2.5-flash"
    ).problemas_produccion()
    assert any("gemini-2.5-flash" in a and "retir" in a for a in avisos)
    _, avisos = ajustes(ia_proveedor="vertex", vertex_proyecto="p").problemas_produccion()
    assert not any("retir" in a for a in avisos)


@pytest.mark.parametrize(
    ("region", "host"),
    [
        ("global", "aiplatform.googleapis.com"),
        ("us", "aiplatform.us.rep.googleapis.com"),
        ("eu", "aiplatform.eu.rep.googleapis.com"),
        ("us-central1", "us-central1-aiplatform.googleapis.com"),
    ],
)
def test_url_de_cada_tipo_de_region(region, host):
    assert vertex_url("p", region, "m", "generateContent") == (
        f"https://{host}/v1/projects/p/locations/{region}/publishers/google/models/m:generateContent"
    )


# ---------- un modelo que ya no existe ----------
@respx.mock
async def test_si_el_modelo_no_existe_responde_el_siguiente():
    retirado = respx.post(f"{BASE}/models/retirado:generateContent").mock(
        return_value=httpx.Response(404, json={"error": {"status": "NOT_FOUND"}})
    )
    respx.post(f"{BASE}/models/vigente:generateContent").mock(return_value=ok({"a": 1}))
    llm = GeminiLLM(["retirado", "vigente"], api_key="k", base_url=BASE, reintentos=2)
    r = await llm.generar_json("s", "p", {})
    assert r.modelo == "vigente" and retirado.call_count == 1  # un 404 no se reintenta
    await llm.generar_json("s", "p", {})
    assert retirado.call_count == 1  # ni se vuelve a pedir enseguida


@respx.mock
async def test_si_ningun_modelo_existe_cuenta_para_el_cortacircuitos():
    ruta = respx.post(url__regex=rf"{BASE}/models/.*").mock(return_value=httpx.Response(404))
    llm = LLMConRespaldo(
        [("vertex", GeminiLLM(["a", "b"], api_key="k", base_url=BASE, reintentos=1))],
        fallos_para_abrir=1,
    )
    with pytest.raises(ErrorLLM, match="HTTP 404"):
        await llm.generar_json("s", "p", {})
    assert ruta.call_count == 2
    assert llm._circuito("vertex").abierto_hasta > 0


# ---------- precios ----------
def test_los_modelos_por_defecto_tienen_precio_propio():
    for proveedor in ("gemini_api", "vertex"):
        s = ajustes(ia_proveedor=proveedor)
        for modelo in [s.llm_model, *s.llm_modelos_respaldo, s.claude_modelo]:
            assert modelo in PRECIOS_REFERENCIA, modelo


def test_precio_de_lista_de_los_modelos_de_vertex():
    c = ControlDeCosto()
    # Precio de lista en «global» (sin la devolución promocional, para que el tope no se quede corto).
    assert c.costo("gemini-3.8-flash", Uso(1_000_000, 1_000_000)) == pytest.approx(9.0)
    assert c.costo("gemini-3.5-flash", Uso(1_000_000, 1_000_000)) == pytest.approx(10.5)
