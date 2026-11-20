"""API interna del agente: token compartido, entrega de documentos y aislamiento por tenant."""

import uuid

import psycopg
import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from tests.conftest import Org, interno
from tests.fakes import ColaFalsa, subir
from tests.pdfs import pdf

NINGUNO = uuid.uuid4()

RUTAS = [
    ("POST", f"/internal/v1/documentos/{NINGUNO}/procesar", None),
    ("POST", "/internal/v1/consultas", {}),
    ("GET", "/internal/v1/consultas", None),
    ("GET", "/internal/v1/embeddings/modelos", None),
    ("POST", "/internal/v1/reindexaciones", {}),
    ("GET", "/internal/v1/reindexaciones", None),
]


@pytest.mark.parametrize(("metodo", "ruta", "cuerpo"), RUTAS)
async def test_sin_token_o_con_token_incorrecto_es_401(client: AsyncClient, metodo, ruta, cuerpo):
    for cabeceras in ({}, {"X-Internal-Token": "incorrecto"}, {"X-Internal-Token": ""}):
        r = await client.request(metodo, ruta, headers=cabeceras, json=cuerpo)
        assert r.status_code == 401, (cabeceras, r.text)


@pytest.mark.parametrize(("metodo", "ruta", "cuerpo"), RUTAS)
async def test_sin_token_configurado_todo_responde_503(
    client: AsyncClient, monkeypatch, metodo, ruta, cuerpo
):
    monkeypatch.setattr(get_settings(), "internal_token", "")
    r = await client.request(metodo, ruta, headers=interno(), json=cuerpo)
    assert r.status_code == 503


async def test_no_existen_rutas_de_usuarios_ni_publicas(client: AsyncClient):
    # El agente no autentica ni expone la API pública: eso es de la API Java.
    for ruta in ("/api/v1/auth/login", "/api/v1/expedientes", "/api/v1/usuarios"):
        assert (await client.get(ruta, headers=interno())).status_code == 404


async def test_health_no_exige_token(client: AsyncClient):
    assert (await client.get("/health")).status_code == 200


# ---------- Entrega de documentos desde Java ----------
async def test_procesar_encola_un_documento_en_cola(client, org_a: Org, cola: ColaFalsa):
    exp = await org_a.crear_expediente()
    doc_id = uuid.UUID((await subir(exp["id"], pdf())).json()["id"])
    r = await client.post(f"/internal/v1/documentos/{doc_id}/procesar", headers=interno())
    assert r.status_code == 202, r.text
    assert r.json() == {"documento_id": str(doc_id), "estado": "EN_COLA"}
    assert cola.encolados == [doc_id]


async def test_procesar_documento_inexistente_es_404(client, cola: ColaFalsa):
    r = await client.post(f"/internal/v1/documentos/{uuid.uuid4()}/procesar", headers=interno())
    assert r.status_code == 404
    assert cola.encolados == []


async def test_procesar_solo_acepta_documentos_en_cola(client, org_a: Org, cola: ColaFalsa):
    exp = await org_a.crear_expediente()
    doc_id = uuid.UUID((await subir(exp["id"], pdf())).json()["id"])
    with psycopg.connect(org_a.postgres_url) as conn:
        conn.execute(
            "UPDATE documentos SET estado_indexacion = 'VALIDANDO' WHERE id = %s", (doc_id,)
        )
    r = await client.post(f"/internal/v1/documentos/{doc_id}/procesar", headers=interno())
    assert r.status_code == 409 and "VALIDANDO" in r.json()["detail"]
    assert cola.encolados == []


async def test_si_la_cola_falla_responde_503_para_que_java_reintente(
    client, org_a: Org, app, monkeypatch
):
    from app.services.cola import get_cola

    app.dependency_overrides[get_cola] = lambda: ColaFalsa(falla=True)
    exp = await org_a.crear_expediente()
    doc_id = uuid.UUID((await subir(exp["id"], pdf())).json()["id"])
    r = await client.post(f"/internal/v1/documentos/{doc_id}/procesar", headers=interno())
    assert r.status_code == 503
    assert "redis" not in r.text.lower()  # sin detalles internos


# ---------- Aislamiento por tenant ----------
async def test_historial_y_reindexaciones_se_acotan_al_tenant_y_al_usuario(
    client, org_a: Org, org_b: Org, cola
):
    exp = await org_a.crear_expediente()
    with psycopg.connect(org_a.postgres_url) as conn:
        conn.execute(
            "INSERT INTO consultas (tenant_id, expediente_id, usuario_id, pregunta, respuesta, "
            "sin_evidencia, modelo_embeddings, latencia_ms) VALUES (%s, %s, %s, 'p', "
            "'{\"consultaId\": \"x\"}', false, 'm', 5)",
            (org_a.tenant_id, uuid.UUID(exp["id"]), org_a.admin_id),
        )
    parametros = {"tenant_id": str(org_a.tenant_id), "expediente_id": exp["id"]}
    propio = await client.get(
        "/internal/v1/consultas",
        headers=interno(),
        params={**parametros, "usuario_id": str(org_a.admin_id)},
    )
    assert len(propio.json()) == 1
    # Otro usuario, o el mismo expediente pedido como si fuera de otro tenant: nada.
    otro_usuario = await client.get(
        "/internal/v1/consultas",
        headers=interno(),
        params={**parametros, "usuario_id": str(uuid.uuid4())},
    )
    assert otro_usuario.json() == []
    otro_tenant = await client.get(
        "/internal/v1/consultas",
        headers=interno(),
        params={
            "tenant_id": str(org_b.tenant_id),
            "expediente_id": exp["id"],
            "usuario_id": str(org_a.admin_id),
        },
    )
    assert otro_tenant.json() == []
    assert (
        await client.get(
            "/internal/v1/reindexaciones",
            headers=interno(),
            params={"tenant_id": str(org_b.tenant_id), "expediente_id": exp["id"]},
        )
    ).json() == []
