from httpx import AsyncClient

from tests.conftest import Org


async def test_crear_y_listar_expediente(client: AsyncClient, org_a: Org):
    exp = await org_a.crear_expediente(org_a.admin)
    assert exp["mi_permiso"] == "ADMIN"
    assert exp["embedding_model_activo"] == "gemini-embedding-001"
    assert exp["embedding_dimension"] == 1536

    lista = (await client.get("/api/v1/expedientes", headers=org_a.admin)).json()
    assert [e["id"] for e in lista] == [exp["id"]]


async def test_codigo_duplicado_en_mismo_tenant_da_409(client: AsyncClient, org_a: Org):
    await org_a.crear_expediente(org_a.admin, "LIC-9")
    r = await client.post(
        "/api/v1/expedientes",
        headers=org_a.admin,
        json={"codigo_expediente": "LIC-9", "titulo": "x", "tipo_expediente": "AUDITORIA_CLINICA"},
    )
    assert r.status_code == 409


async def test_mismo_codigo_en_otro_tenant_es_valido(client: AsyncClient, org_a: Org, org_b: Org):
    await org_a.crear_expediente(org_a.admin, "LIC-9")
    await org_b.crear_expediente(org_b.admin, "LIC-9")


async def test_lector_no_puede_crear(client: AsyncClient, org_a: Org):
    _, lector = await org_a.crear_usuario("lector@hospital-a.co", "LECTOR")
    r = await client.post(
        "/api/v1/expedientes",
        headers=lector,
        json={"codigo_expediente": "X", "titulo": "x", "tipo_expediente": "AUDITORIA_CLINICA"},
    )
    assert r.status_code == 403


async def test_aislamiento_entre_tenants(client: AsyncClient, org_a: Org, org_b: Org):
    exp = await org_a.crear_expediente(org_a.admin)
    url = f"/api/v1/expedientes/{exp['id']}"

    # El admin de B no ve, no edita ni borra el expediente de A (404, no revela existencia).
    assert (await client.get(url, headers=org_b.admin)).status_code == 404
    assert (
        await client.patch(url, headers=org_b.admin, json={"titulo": "hack"})
    ).status_code == 404
    assert (await client.delete(url, headers=org_b.admin)).status_code == 404
    assert (await client.get(f"{url}/permisos", headers=org_b.admin)).status_code == 404
    assert (await client.get("/api/v1/expedientes", headers=org_b.admin)).json() == []


async def test_no_se_asigna_permiso_a_usuario_de_otro_tenant(
    client: AsyncClient, org_a: Org, org_b: Org
):
    exp = await org_a.crear_expediente(org_a.admin)
    uid_b, _ = await org_b.crear_usuario("auditor@clinica-b.co", "AUDITOR_MEDICO")
    r = await client.put(
        f"/api/v1/expedientes/{exp['id']}/permisos/{uid_b}",
        headers=org_a.admin,
        json={"permiso": "LECTOR"},
    )
    assert r.status_code == 404


async def test_usuario_sin_permiso_no_ve_el_expediente(client: AsyncClient, org_a: Org):
    exp = await org_a.crear_expediente(org_a.admin)
    _, juridico = await org_a.crear_usuario("juridico@hospital-a.co", "JURIDICO")
    assert (
        await client.get(f"/api/v1/expedientes/{exp['id']}", headers=juridico)
    ).status_code == 404
    assert (await client.get("/api/v1/expedientes", headers=juridico)).json() == []


async def test_niveles_de_permiso(client: AsyncClient, org_a: Org):
    exp = await org_a.crear_expediente(org_a.admin)
    url = f"/api/v1/expedientes/{exp['id']}"
    uid_lector, lector = await org_a.crear_usuario("lector@hospital-a.co", "LECTOR")
    uid_editor, editor = await org_a.crear_usuario("bio@hospital-a.co", "BIOMEDICO")

    for uid, permiso in ((uid_lector, "LECTOR"), (uid_editor, "EDITOR")):
        r = await client.put(
            f"{url}/permisos/{uid}", headers=org_a.admin, json={"permiso": permiso}
        )
        assert r.status_code == 200, r.text

    # LECTOR: ve, no edita.
    r = await client.get(url, headers=lector)
    assert r.status_code == 200 and r.json()["mi_permiso"] == "LECTOR"
    assert (await client.patch(url, headers=lector, json={"titulo": "x"})).status_code == 403

    # EDITOR: edita, pero no borra ni gestiona permisos.
    r = await client.patch(
        url, headers=editor, json={"titulo": "Nuevo título", "estado": "CERRADO"}
    )
    assert r.status_code == 200 and r.json()["estado"] == "CERRADO"
    assert (await client.delete(url, headers=editor)).status_code == 403
    assert (await client.get(f"{url}/permisos", headers=editor)).status_code == 403

    # ADMIN_TENANT: borra.
    assert (await client.delete(url, headers=org_a.admin)).status_code == 204
    assert (await client.get(url, headers=org_a.admin)).status_code == 404


async def test_creador_es_admin_del_expediente(client: AsyncClient, org_a: Org):
    uid, auditor = await org_a.crear_usuario("auditor@hospital-a.co", "AUDITOR_MEDICO")
    exp = await org_a.crear_expediente(auditor, "AUD-1")
    permisos = (
        await client.get(f"/api/v1/expedientes/{exp['id']}/permisos", headers=auditor)
    ).json()
    assert permisos == [
        {
            "usuario_id": uid,
            "email": "auditor@hospital-a.co",
            "nombre_completo": "auditor",
            "permiso": "ADMIN",
        }
    ]


async def test_no_se_puede_quitar_el_ultimo_admin(client: AsyncClient, org_a: Org):
    uid, auditor = await org_a.crear_usuario("auditor@hospital-a.co", "AUDITOR_MEDICO")
    exp = await org_a.crear_expediente(auditor, "AUD-2")
    url = f"/api/v1/expedientes/{exp['id']}/permisos/{uid}"
    assert (await client.delete(url, headers=org_a.admin)).status_code == 409
    assert (
        await client.put(url, headers=org_a.admin, json={"permiso": "LECTOR"})
    ).status_code == 409


async def test_revocar_permiso(client: AsyncClient, org_a: Org):
    exp = await org_a.crear_expediente(org_a.admin)
    uid, lector = await org_a.crear_usuario("lector@hospital-a.co", "LECTOR")
    url = f"/api/v1/expedientes/{exp['id']}"
    await client.put(f"{url}/permisos/{uid}", headers=org_a.admin, json={"permiso": "LECTOR"})
    assert (await client.get(url, headers=lector)).status_code == 200
    assert (await client.delete(f"{url}/permisos/{uid}", headers=org_a.admin)).status_code == 204
    assert (await client.get(url, headers=lector)).status_code == 404


async def test_valores_invalidos_rechazados(client: AsyncClient, org_a: Org):
    r = await client.post(
        "/api/v1/expedientes",
        headers=org_a.admin,
        json={"codigo_expediente": "X", "titulo": "x", "tipo_expediente": "INVENTADO"},
    )
    assert r.status_code == 422
