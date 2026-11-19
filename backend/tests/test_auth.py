from httpx import AsyncClient

from tests.conftest import Org, auth, registrar_org


async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": "ok"}


async def test_registro_y_me(client: AsyncClient, org_a: Org):
    r = await client.get("/api/v1/auth/me", headers=org_a.admin)
    assert r.status_code == 200
    assert r.json()["rol_global"] == "ADMIN_TENANT"
    assert "password_hash" not in r.json()


async def test_nit_duplicado_da_409(client: AsyncClient, org_a: Org):
    r = await client.post(
        "/api/v1/auth/registro-tenant",
        json={
            "tenant_nombre": "Otro",
            "nit": "900111",
            "admin_email": "otro@x.co",
            "admin_password": "ClaveSegura123",
            "admin_nombre": "Otro",
        },
    )
    assert r.status_code == 409


async def test_login_credenciales_invalidas(client: AsyncClient, org_a: Org):
    r = await client.post(
        "/api/v1/auth/login", json={"email": "admin@hospital-a.co", "password": "incorrecta"}
    )
    assert r.status_code == 401
    r = await client.post(
        "/api/v1/auth/login", json={"email": "noexiste@x.co", "password": "incorrecta"}
    )
    assert r.status_code == 401


async def test_sin_token_y_token_basura(client: AsyncClient):
    assert (await client.get("/api/v1/expedientes")).status_code == 401
    r = await client.get("/api/v1/expedientes", headers=auth("no-es-un-jwt"))
    assert r.status_code == 401


async def test_refresh_no_sirve_como_access(client: AsyncClient):
    r = await client.post(
        "/api/v1/auth/registro-tenant",
        json={
            "tenant_nombre": "Hospital H",
            "nit": "900333",
            "admin_email": "a@h.co",
            "admin_password": "ClaveSegura123",
            "admin_nombre": "Admin H",
        },
    )
    assert r.status_code == 201, r.text
    tokens = r.json()
    assert (
        await client.get("/api/v1/auth/me", headers=auth(tokens["refresh_token"]))
    ).status_code == 401

    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    assert (
        await client.get("/api/v1/auth/me", headers=auth(r.json()["access_token"]))
    ).status_code == 200

    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert r.status_code == 401


async def test_usuario_desactivado_pierde_acceso_inmediato(client: AsyncClient, org_a: Org):
    uid, headers = await org_a.crear_usuario("juridico@hospital-a.co", "JURIDICO")
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 200

    r = await client.patch(f"/api/v1/usuarios/{uid}", headers=org_a.admin, json={"activo": False})
    assert r.status_code == 200
    # El token sigue vigente, pero el usuario ya no está activo.
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401


async def test_admin_no_puede_desactivarse(client: AsyncClient, org_a: Org):
    me = (await client.get("/api/v1/auth/me", headers=org_a.admin)).json()
    r = await client.patch(
        f"/api/v1/usuarios/{me['id']}", headers=org_a.admin, json={"activo": False}
    )
    assert r.status_code == 409


async def test_solo_admin_tenant_gestiona_usuarios(client: AsyncClient, org_a: Org):
    _, headers = await org_a.crear_usuario("bio@hospital-a.co", "BIOMEDICO")
    assert (await client.get("/api/v1/usuarios", headers=headers)).status_code == 403
    assert (await client.get("/api/v1/tenant", headers=headers)).status_code == 403


async def test_politica_borrado_del_tenant(client: AsyncClient, org_a: Org):
    r = await client.patch(
        "/api/v1/tenant", headers=org_a.admin, json={"politica_borrado": "DIFERIDO_1H"}
    )
    assert r.status_code == 200
    assert r.json()["politica_borrado"] == "DIFERIDO_1H"
    r = await client.patch(
        "/api/v1/tenant", headers=org_a.admin, json={"politica_borrado": "NUNCA"}
    )
    assert r.status_code == 422


async def test_admin_de_otro_tenant_no_ve_usuarios_ajenos(client: AsyncClient, org_a: Org):
    uid, _ = await org_a.crear_usuario("lector@hospital-a.co", "LECTOR")
    org_b = await registrar_org(client, "900444", "admin@b.co")
    usuarios_b = (await client.get("/api/v1/usuarios", headers=org_b.admin)).json()
    assert all(u["id"] != uid for u in usuarios_b)
    r = await client.patch(f"/api/v1/usuarios/{uid}", headers=org_b.admin, json={"activo": False})
    assert r.status_code == 404
