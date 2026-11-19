"""Logs estructurados, request id, cabeceras y métricas Prometheus."""

import json
import logging

import pytest
from httpx import AsyncClient

from app.core import contexto
from app.core.config import get_settings
from app.core.logs import FormatoJson, FormatoTexto
from app.main import create_app
from tests.conftest import Org

TOKEN = {"Authorization": "Bearer token-de-metricas-de-pruebas"}


# ---------- Request ID ----------
async def test_request_id_generado_y_devuelto(client: AsyncClient):
    r = await client.get("/health")
    assert len(r.headers["x-request-id"]) == 32
    otro = await client.get("/health")
    assert otro.headers["x-request-id"] != r.headers["x-request-id"]


async def test_request_id_valido_de_caddy_se_respeta_y_el_invalido_se_ignora(client: AsyncClient):
    r = await client.get("/health", headers={"X-Request-ID": "req-abc12345"})
    assert r.headers["x-request-id"] == "req-abc12345"
    # Un valor con caracteres peligrosos (inyección en logs) se descarta.
    r = await client.get("/health", headers={"X-Request-ID": "x\nforja: 1"})
    assert "\n" not in r.headers["x-request-id"] and len(r.headers["x-request-id"]) == 32


async def test_respuestas_de_la_api_no_se_cachean(client: AsyncClient, org_a: Org):
    r = await client.get("/api/v1/expedientes", headers=org_a.admin)
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "cache-control" not in (await client.get("/health")).headers


# ---------- Formato de logs ----------
def _registro(mensaje="hola", **extra) -> logging.LogRecord:
    r = logging.LogRecord("app.prueba", logging.INFO, __file__, 1, mensaje, None, None)
    r.__dict__.update(extra)
    return r


def test_log_json_incluye_contexto_y_campos_extra():
    t1 = contexto.request_id.set("rid-123456789")
    t2 = contexto.usuario_id.set("u-1")
    try:
        linea = json.loads(FormatoJson().format(_registro("consulta", codigo=200, duracion_ms=12)))
    finally:
        contexto.usuario_id.reset(t2)
        contexto.request_id.reset(t1)
    assert linea["mensaje"] == "consulta" and linea["nivel"] == "INFO"
    assert linea["request_id"] == "rid-123456789" and linea["usuario_id"] == "u-1"
    assert linea["codigo"] == 200 and linea["duracion_ms"] == 12
    assert "tenant_id" not in linea  # sin contexto no se inventa


def test_log_json_serializa_excepciones_y_tildes():
    try:
        raise ValueError("falló la verificación")
    except ValueError:
        import sys

        r = _registro("error")
        r.exc_info = sys.exc_info()
    linea = json.loads(FormatoJson().format(r))
    assert "ValueError: falló la verificación" in linea["excepcion"]


def test_log_texto_muestra_prefijo_de_request():
    token = contexto.request_id.set("abcdef123456")
    try:
        assert "[abcdef12]" in FormatoTexto().format(_registro())
    finally:
        contexto.request_id.reset(token)


async def test_el_log_de_acceso_lleva_ruta_plantilla_sin_datos_sensibles(
    client: AsyncClient, org_a: Org, caplog
):
    exp = await org_a.crear_expediente(org_a.admin)
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="medtender.acceso"):
        await client.get(f"/api/v1/expedientes/{exp['id']}?secreto=abc", headers=org_a.admin)
    registro = next(r for r in caplog.records if r.name == "medtender.acceso")
    assert registro.ruta == "/api/v1/expedientes/{expediente_id}"
    assert registro.codigo == 200
    assert "secreto" not in registro.getMessage() and "Bearer" not in registro.getMessage()


# ---------- Métricas ----------
async def test_metrics_exige_token(client: AsyncClient):
    assert (await client.get("/metrics")).status_code == 401
    assert (
        await client.get("/metrics", headers={"Authorization": "Bearer otro"})
    ).status_code == 401
    assert (await client.get("/metrics", headers=TOKEN)).status_code == 200


async def test_metrics_en_produccion_sin_token_no_existe(client: AsyncClient, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "metrics_token", "")
    monkeypatch.setattr(s, "entorno", "produccion")
    assert (await client.get("/metrics")).status_code == 404
    monkeypatch.setattr(s, "entorno", "desarrollo")
    assert (await client.get("/metrics")).status_code == 200  # abierto solo en desarrollo


async def test_metricas_http_usan_plantilla_de_ruta(client: AsyncClient, org_a: Org):
    exp = await org_a.crear_expediente(org_a.admin)
    await client.get(f"/api/v1/expedientes/{exp['id']}", headers=org_a.admin)
    texto = (await client.get("/metrics", headers=TOKEN)).text
    assert 'ruta="/api/v1/expedientes/{expediente_id}"' in texto
    assert exp["id"] not in texto  # los ids no pueden convertirse en etiquetas
    assert "medtender_http_duracion_segundos_bucket" in texto


async def test_medidores_del_negocio_vienen_de_la_base_de_datos(
    client: AsyncClient, org_a: Org, scanner, cola
):
    from tests.fakes import subir
    from tests.pdfs import pdf

    exp = await org_a.crear_expediente(org_a.admin)
    r = await subir(client, org_a.admin, exp["id"], pdf())
    assert r.status_code == 202
    texto = (await client.get("/metrics", headers=TOKEN)).text
    assert 'medtender_documentos{estado="EN_COLA"} 1.0' in texto
    assert "medtender_pdf_temporales_pendientes 1.0" in texto
    assert "medtender_fragmentos 0.0" in texto
    assert "medtender_documentos_en_proceso_mas_de_1h 0.0" in texto


async def test_estado_de_medidores_no_arrastra_etiquetas_viejas(
    client: AsyncClient, org_a: Org, scanner, cola
):
    from tests.fakes import subir
    from tests.pdfs import pdf

    exp = await org_a.crear_expediente(org_a.admin)
    doc = (await subir(client, org_a.admin, exp["id"], pdf())).json()
    assert 'estado="EN_COLA"' in (await client.get("/metrics", headers=TOKEN)).text
    await client.delete(
        f"/api/v1/expedientes/{exp['id']}/documentos/{doc['id']}", headers=org_a.admin
    )
    # Sin documentos, la etiqueta EN_COLA desaparece en vez de quedarse con el valor anterior.
    assert 'estado="EN_COLA"' not in (await client.get("/metrics", headers=TOKEN)).text


# ---------- Documentación ----------
@pytest.mark.parametrize("ruta", ["/docs", "/openapi.json", "/redoc"])
async def test_documentacion_deshabilitada_en_produccion(monkeypatch, ruta):
    from httpx import ASGITransport

    monkeypatch.setattr(get_settings(), "entorno", "produccion")
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        assert (await c.get(ruta)).status_code == 404


async def test_documentacion_disponible_en_desarrollo(client: AsyncClient):
    assert (await client.get("/openapi.json")).status_code == 200
