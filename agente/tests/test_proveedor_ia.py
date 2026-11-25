"""El agente informa qué proveedor de IA recibe de verdad los datos: de ahí sale el texto del
consentimiento que muestra la API."""

import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import proveedor_ia
from app.core.config import Settings
from app.main import create_app

CABECERA = {"X-Internal-Token": os.environ["INTERNAL_TOKEN"]}


async def pedir(monkeypatch, cabeceras=CABECERA, **ajustes):
    s = Settings(**ajustes)
    monkeypatch.setattr(proveedor_ia, "get_settings", lambda: s)
    transporte = ASGITransport(app=create_app())
    async with AsyncClient(transport=transporte, base_url="http://agente") as cliente:
        return await cliente.get("/internal/v1/ia", headers=cabeceras)


@pytest.mark.parametrize(
    ("ajustes", "esperado"),
    [
        ({}, {"proveedor": "gemini_api", "respaldo": ""}),
        (
            {"ia_proveedor": "vertex", "vertex_proyecto": "p"},
            {"proveedor": "vertex", "respaldo": ""},
        ),
        (
            {
                "ia_proveedor": "vertex",
                "llm_respaldo_proveedor": "claude",
                "anthropic_api_key": "k",
            },
            {"proveedor": "vertex", "respaldo": "claude"},
        ),
        # Sin clave no se le puede enviar nada: no se anuncia como respaldo.
        (
            {"llm_respaldo_proveedor": "claude", "anthropic_api_key": ""},
            {"proveedor": "gemini_api", "respaldo": ""},
        ),
    ],
)
async def test_informa_el_proveedor_activo(monkeypatch, ajustes, esperado):
    r = await pedir(monkeypatch, **ajustes)
    assert r.status_code == 200 and r.json() == esperado


async def test_exige_el_token_interno(monkeypatch):
    r = await pedir(monkeypatch, cabeceras={})
    assert r.status_code == 401
