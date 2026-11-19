"""Auditoría de accesos: qué se registra, qué no, aislamiento por tenant e inmutabilidad."""

import psycopg
import pytest
from httpx import AsyncClient

from app.core.metricas import AUDITORIA_FALLOS
from app.ia.embeddings import EmbeddingRouter, get_router
from tests.conftest import Org, auth
from tests.fakes import EmbeddingsFalsos, subir
from tests.pdfs import pdf


async def eventos(client: AsyncClient, org: Org, **filtros) -> list[dict]:
    r = await client.get("/api/v1/auditoria", headers=org.admin, params=filtros)
    assert r.status_code == 200, r.text
    return r.json()


def acciones(evs: list[dict]) -> list[str]:
    return [e["accion"] for e in evs]


# ---------- Autenticación ----------
async def test_login_ok_y_fallido(client: AsyncClient, org_a: Org):
    await client.post(
        "/api/v1/auth/login", json={"email": "Admin@Hospital-A.co", "password": "ClaveSegura123"}
    )
    await client.post(
        "/api/v1/auth/login", json={"email": "admin@hospital-a.co", "password": "mala"}
    )
    evs = await eventos(client, org_a)
    ok = next(e for e in evs if e["accion"] == "LOGIN_OK")
    fallo = next(e for e in evs if e["accion"] == "LOGIN_FALLIDO")
    assert ok["email"] == "admin@hospital-a.co" and ok["resultado"] == "OK"  # normalizado
    assert fallo["resultado"] == "DENEGADO" and fallo["detalle"] == {"motivo": "credenciales"}
    assert ok["ip"] and len(ok["request_id"]) >= 8
    # Ninguna contraseña ni token en el registro.
    assert "ClaveSegura123" not in str(evs) and "mala" not in str(evs)


async def test_login_de_usuario_inactivo_queda_registrado(client: AsyncClient, org_a: Org):
    uid, _ = await org_a.crear_usuario("bio@hospital-a.co", "BIOMEDICO")
    await client.patch(f"/api/v1/usuarios/{uid}", headers=org_a.admin, json={"activo": False})
    r = await client.post(
        "/api/v1/auth/login", json={"email": "bio@hospital-a.co", "password": "ClaveSegura123"}
    )
    assert r.status_code == 401
    fallo = next(e for e in await eventos(client, org_a) if e["accion"] == "LOGIN_FALLIDO")
    assert fallo["detalle"] == {"motivo": "inactivo"} and fallo["usuario_id"] == uid


async def test_registro_del_tenant_queda_auditado(client: AsyncClient, org_a: Org):
    assert "REGISTRO_TENANT" in acciones(await eventos(client, org_a))


# ---------- Administración ----------
async def test_cambio_de_rol_guarda_antes_y_despues(client: AsyncClient, org_a: Org):
    uid, _ = await org_a.crear_usuario("lector@hospital-a.co", "LECTOR")
    await client.patch(
        f"/api/v1/usuarios/{uid}", headers=org_a.admin, json={"rol_global": "JURIDICO"}
    )
    evs = await eventos(client, org_a, accion="USUARIO_ACTUALIZADO")
    assert len(evs) == 1
    assert evs[0]["recurso_id"] == uid
    assert evs[0]["detalle"]["antes"]["rol"] == "LECTOR"
    assert evs[0]["detalle"]["despues"]["rol"] == "JURIDICO"
    assert "USUARIO_CREADO" in acciones(await eventos(client, org_a))


async def test_expedientes_y_permisos(client: AsyncClient, org_a: Org):
    exp = await org_a.crear_expediente(org_a.admin)
    uid, _ = await org_a.crear_usuario("lector@hospital-a.co", "LECTOR")
    url = f"/api/v1/expedientes/{exp['id']}"
    await client.put(f"{url}/permisos/{uid}", headers=org_a.admin, json={"permiso": "LECTOR"})
    await client.patch(url, headers=org_a.admin, json={"titulo": "Nuevo título"})
    await client.delete(f"{url}/permisos/{uid}", headers=org_a.admin)
    await client.delete(url, headers=org_a.admin)

    evs = await eventos(client, org_a, recurso_id=exp["id"])
    assert acciones(evs)[::-1] == [  # cronológico
        "EXPEDIENTE_CREADO",
        "PERMISO_ASIGNADO",
        "EXPEDIENTE_ACTUALIZADO",
        "PERMISO_REVOCADO",
        "EXPEDIENTE_ELIMINADO",
    ]
    asignado = next(e for e in evs if e["accion"] == "PERMISO_ASIGNADO")
    assert asignado["detalle"] == {"destinatario": uid, "permiso": "LECTOR"}
    # El borrado del expediente no borra su rastro.
    assert len(await eventos(client, org_a, accion="EXPEDIENTE_ELIMINADO")) == 1


# ---------- Accesos denegados ----------
async def test_acceso_a_expediente_de_otro_tenant_queda_registrado(
    client: AsyncClient, org_a: Org, org_b: Org
):
    exp = await org_a.crear_expediente(org_a.admin)
    r = await client.get(f"/api/v1/expedientes/{exp['id']}", headers=org_b.admin)
    assert r.status_code == 404  # la respuesta no revela que existe
    denegados = await eventos(client, org_b, resultado="DENEGADO")
    assert len(denegados) == 1
    assert denegados[0]["accion"] == "ACCESO_DENEGADO" and denegados[0]["recurso_id"] == exp["id"]
    assert denegados[0]["detalle"]["motivo"] == "inexistente_o_otro_tenant"
    # El dueño del expediente no ve el intento ajeno en su propio registro.
    assert await eventos(client, org_a, resultado="DENEGADO") == []


async def test_permiso_insuficiente_y_sin_permiso(client: AsyncClient, org_a: Org):
    exp = await org_a.crear_expediente(org_a.admin)
    uid, lector = await org_a.crear_usuario("lector@hospital-a.co", "LECTOR")
    url = f"/api/v1/expedientes/{exp['id']}"
    await client.get(url, headers=lector)  # sin permiso asignado
    await client.put(f"{url}/permisos/{uid}", headers=org_a.admin, json={"permiso": "LECTOR"})
    assert (await client.patch(url, headers=lector, json={"titulo": "x"})).status_code == 403

    motivos = [
        e["detalle"]["motivo"]
        for e in await eventos(client, org_a, usuario_id=uid)
        if e["accion"] == "ACCESO_DENEGADO"
    ]
    assert sorted(motivos) == ["permiso_insuficiente", "sin_permiso"]
    insuf = next(
        e
        for e in await eventos(client, org_a, usuario_id=uid)
        if e["detalle"].get("motivo") == "permiso_insuficiente"
    )
    assert insuf["detalle"] == {
        "motivo": "permiso_insuficiente",
        "requerido": "EDITOR",
        "tiene": "LECTOR",
    }


# ---------- Documentos y consultas ----------
async def test_documentos_guardan_sha256_y_no_contenido(
    client: AsyncClient, org_a: Org, scanner, cola
):
    exp = await org_a.crear_expediente(org_a.admin)
    doc = (await subir(client, org_a.admin, exp["id"], pdf())).json()
    await client.delete(
        f"/api/v1/expedientes/{exp['id']}/documentos/{doc['id']}", headers=org_a.admin
    )
    subido = (await eventos(client, org_a, accion="DOCUMENTO_SUBIDO"))[0]
    assert subido["recurso_id"] == doc["id"]
    assert subido["detalle"]["sha256"] == doc["sha256_original"]
    assert (
        subido["detalle"]["tipo"] == "PLIEGO" and subido["detalle"]["bytes"] == doc["tamano_bytes"]
    )
    assert len(await eventos(client, org_a, accion="DOCUMENTO_ELIMINADO")) == 1


async def test_consulta_se_audita_sin_el_texto_de_la_pregunta(client: AsyncClient, app, org_a: Org):
    app.dependency_overrides[get_router] = lambda: EmbeddingRouter(
        {"gemini-embedding-001": EmbeddingsFalsos("gemini-embedding-001", 1536)}
    )
    exp = await org_a.crear_expediente(org_a.admin)
    pregunta = "¿Cuál es el precio confidencial de la oferta del proveedor ACME?"
    r = await client.post(
        f"/api/v1/expedientes/{exp['id']}/consultas",
        headers=org_a.admin,
        json={"pregunta": pregunta},
    )
    ev = (await eventos(client, org_a, accion="CONSULTA_RAG"))[0]
    assert ev["detalle"]["consulta"] == r.json()["consultaId"]
    assert ev["detalle"]["sin_evidencia"] is True and ev["recurso_id"] == exp["id"]
    assert "ACME" not in str(ev) and "precio" not in str(ev)


# ---------- Acceso al registro ----------
async def test_solo_el_administrador_lee_la_auditoria(client: AsyncClient, org_a: Org):
    _, juridico = await org_a.crear_usuario("juridico@hospital-a.co", "JURIDICO")
    assert (await client.get("/api/v1/auditoria", headers=juridico)).status_code == 403
    assert (await client.get("/api/v1/auditoria")).status_code == 401


async def test_aislamiento_entre_tenants(client: AsyncClient, org_a: Org, org_b: Org):
    await org_a.crear_expediente(org_a.admin)
    assert "EXPEDIENTE_CREADO" in acciones(await eventos(client, org_a))
    assert "EXPEDIENTE_CREADO" not in acciones(await eventos(client, org_b))
    ids_a = {e["usuario_id"] for e in await eventos(client, org_a) if e["usuario_id"]}
    ids_b = {e["usuario_id"] for e in await eventos(client, org_b) if e["usuario_id"]}
    assert not ids_a & ids_b


async def test_filtros_y_paginacion(client: AsyncClient, org_a: Org):
    for i in range(5):
        await org_a.crear_expediente(org_a.admin, f"E-{i}")
    todos = await eventos(client, org_a, accion="EXPEDIENTE_CREADO")
    assert len(todos) == 5
    pagina = await eventos(client, org_a, accion="EXPEDIENTE_CREADO", limit=2, offset=1)
    assert [e["id"] for e in pagina] == [e["id"] for e in todos[1:3]]
    assert (
        await client.get("/api/v1/auditoria", headers=org_a.admin, params={"resultado": "X"})
    ).status_code == 422
    assert (
        await client.get("/api/v1/auditoria", headers=org_a.admin, params={"limit": 9999})
    ).status_code == 422
    futuro = await eventos(client, org_a, desde="2099-01-01T00:00:00Z")
    assert futuro == []


# ---------- Inmutabilidad ----------
def test_la_tabla_es_de_solo_anexado(postgres_url):
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        conn.execute("INSERT INTO auditoria (accion, resultado) VALUES ('PRUEBA', 'OK')")
        with pytest.raises(psycopg.errors.RaiseException, match="solo de anexado|solo anexado"):
            conn.execute("UPDATE auditoria SET resultado = 'ERROR' WHERE accion = 'PRUEBA'")
        with pytest.raises(psycopg.errors.RaiseException, match="DELETE"):
            conn.execute("DELETE FROM auditoria WHERE accion = 'PRUEBA'")
        assert conn.execute(
            "SELECT count(*) FROM auditoria WHERE accion = 'PRUEBA'"
        ).fetchone() == (1,)


# ---------- Resiliencia ----------
async def test_un_fallo_al_auditar_no_tumba_la_peticion(
    client: AsyncClient, org_a: Org, monkeypatch
):
    from app.services import auditoria

    def sin_base_de_datos():
        raise ConnectionError("base de datos de auditoría caída")

    monkeypatch.setattr(auditoria, "get_sessionmaker", sin_base_de_datos)
    antes = AUDITORIA_FALLOS._value.get()
    r = await client.post(
        "/api/v1/expedientes",
        headers=org_a.admin,
        json={
            "codigo_expediente": "X-1",
            "titulo": "Título",
            "tipo_expediente": "AUDITORIA_CLINICA",
        },
    )
    assert r.status_code == 201
    assert AUDITORIA_FALLOS._value.get() == antes + 1


async def test_token_de_otro_tenant_no_lee_la_auditoria_ajena(
    client: AsyncClient, org_a: Org, org_b: Org
):
    """El tenant sale del usuario autenticado; no hay parámetro para elegirlo."""
    tid_a = (await client.get("/api/v1/auth/me", headers=org_a.admin)).json()["tenant_id"]
    r = await client.get("/api/v1/auditoria", headers=org_b.admin, params={"tenant_id": tid_a})
    assert all(e["email"] != "admin@hospital-a.co" for e in r.json())
    assert auth("x") != org_b.admin
