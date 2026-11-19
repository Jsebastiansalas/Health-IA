"""Límites de peticiones: almacén (memoria y Redis real) y reglas aplicadas a los endpoints."""

import time
import uuid

import pytest
from httpx import AsyncClient
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

from app.core import limites
from app.core.config import get_settings
from app.core.limites import AlmacenMemoria, AlmacenRedis
from app.core.metricas import LIMITE_FALLOS, LIMITE_RECHAZOS
from app.ia.embeddings import EmbeddingRouter, get_router
from tests.conftest import Org, registrar_org
from tests.fakes import EmbeddingsFalsos, archivos, subir
from tests.pdfs import pdf


def _valor(contador, **etiquetas) -> float:
    return contador.labels(**etiquetas)._value.get() if etiquetas else contador._value.get()


@pytest.fixture
def ajustar(monkeypatch):
    """ajustar(rl_login_ip_min=3, ...) cambia la configuración solo durante la prueba."""

    def _ajustar(**valores):
        s = get_settings()
        for k, v in valores.items():
            monkeypatch.setattr(s, k, v)

    return _ajustar


# ---------- Almacén en memoria ----------
async def test_memoria_cuenta_y_expira(monkeypatch):
    reloj = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: reloj[0])
    a = AlmacenMemoria()
    assert await a.golpear("k", 60) == (1, 60)
    assert (await a.golpear("k", 60))[0] == 2
    assert await a.contar("k") == (2, 60)
    reloj[0] += 61
    assert await a.contar("k") == (0, 0)
    assert (await a.golpear("k", 60))[0] == 1  # ventana nueva


async def test_la_ventana_no_se_extiende_con_cada_golpe(monkeypatch):
    reloj = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: reloj[0])
    a = AlmacenMemoria()
    await a.golpear("k", 60)
    reloj[0] = 59
    await a.golpear("k", 60)
    reloj[0] = 61
    assert (await a.golpear("k", 60))[0] == 1  # ventana fija: la original ya venció


# ---------- Almacén Redis real ----------
@pytest.fixture(scope="module")
def redis_url():
    with DockerContainer("redis:7-alpine").with_exposed_ports(6379) as c:
        wait_for_logs(c, "Ready to accept connections")
        yield f"redis://{c.get_container_host_ip()}:{c.get_exposed_port(6379)}/0"


async def test_redis_contador_atomico_con_ttl(redis_url):
    a = AlmacenRedis(redis_url)
    try:
        await a.reiniciar()
        for esperado in (1, 2, 3):
            cuenta, ttl = await a.golpear("rl:prueba:60:x", 60)
            assert cuenta == esperado and 1 <= ttl <= 60
        assert (await a.contar("rl:prueba:60:x"))[0] == 3
        assert await a.contar("rl:no-existe") == (0, 0)
        await a.reiniciar()
        assert await a.contar("rl:prueba:60:x") == (0, 0)
    finally:
        await a.cerrar()


async def test_redis_concurrencia_no_pierde_golpes(redis_url):
    import asyncio

    a = AlmacenRedis(redis_url)
    try:
        await a.reiniciar()
        resultados = await asyncio.gather(*[a.golpear("rl:carrera:60:x", 60) for _ in range(200)])
        assert sorted(c for c, _ in resultados) == list(range(1, 201))
    finally:
        await a.cerrar()


async def test_redis_la_clave_siempre_tiene_expiracion(redis_url):
    import redis.asyncio as aioredis

    a = AlmacenRedis(redis_url)
    r = aioredis.from_url(redis_url)
    try:
        await a.golpear("rl:ttl:30:x", 30)
        assert 0 < await r.ttl("rl:ttl:30:x") <= 30  # nunca -1 (eterna)
    finally:
        await a.cerrar()
        await r.aclose()


# ---------- Reglas sobre los endpoints ----------
async def test_login_limite_por_ip(client: AsyncClient, org_a: Org, ajustar):
    ajustar(rl_login_ip_min=3)
    cuerpo = {"email": "admin@hospital-a.co", "password": "ClaveSegura123"}
    for _ in range(3):
        assert (await client.post("/api/v1/auth/login", json=cuerpo)).status_code == 200
    antes = _valor(LIMITE_RECHAZOS, regla="login_ip")
    r = await client.post("/api/v1/auth/login", json=cuerpo)
    assert r.status_code == 429
    assert 1 <= int(r.headers["retry-after"]) <= 60
    assert "Demasiadas solicitudes" in r.json()["detail"]
    assert _valor(LIMITE_RECHAZOS, regla="login_ip") == antes + 1


async def test_login_bloquea_el_par_ip_correo_tras_varios_fallos(
    client: AsyncClient, org_a: Org, ajustar
):
    ajustar(rl_login_fallos_par=3, confiar_proxy=True)
    mala = {"email": "admin@hospital-a.co", "password": "incorrecta"}
    buena = {"email": "admin@hospital-a.co", "password": "ClaveSegura123"}
    atacante = {"X-Forwarded-For": "203.0.113.7"}
    for _ in range(3):
        r = await client.post("/api/v1/auth/login", json=mala, headers=atacante)
        assert r.status_code == 401
    # Desde esa IP, ni siquiera la contraseña correcta pasa mientras dure el bloqueo.
    assert (
        await client.post("/api/v1/auth/login", json=buena, headers=atacante)
    ).status_code == 429
    # El usuario legítimo, desde su propia IP, no queda afectado por el atacante.
    legitimo = {"X-Forwarded-For": "198.51.100.20"}
    assert (
        await client.post("/api/v1/auth/login", json=buena, headers=legitimo)
    ).status_code == 200
    # Y el atacante tampoco queda bloqueado para otros correos (no hay enumeración por bloqueo).
    otro = {"email": "otro@x.co", "password": "x"}
    assert (await client.post("/api/v1/auth/login", json=otro, headers=atacante)).status_code == 401


async def test_login_exitoso_no_cuenta_como_fallo(client: AsyncClient, org_a: Org, ajustar):
    ajustar(rl_login_fallos_par=2)
    buena = {"email": "admin@hospital-a.co", "password": "ClaveSegura123"}
    for _ in range(6):
        assert (await client.post("/api/v1/auth/login", json=buena)).status_code == 200


async def test_ip_de_x_forwarded_for_solo_si_se_confia_en_el_proxy(
    client: AsyncClient, org_a: Org, ajustar
):
    ajustar(rl_login_ip_min=2, confiar_proxy=False)
    cuerpo = {"email": "admin@hospital-a.co", "password": "ClaveSegura123"}
    # Sin confiar en el proxy, falsear la cabecera no sirve para evadir el límite.
    for i in range(2):
        r = await client.post(
            "/api/v1/auth/login", json=cuerpo, headers={"X-Forwarded-For": f"1.1.1.{i}"}
        )
        assert r.status_code == 200
    r = await client.post("/api/v1/auth/login", json=cuerpo, headers={"X-Forwarded-For": "9.9.9.9"})
    assert r.status_code == 429


async def test_x_forwarded_for_toma_la_ultima_entrada(client: AsyncClient, org_a: Org, ajustar):
    """Caddy añade la IP real al final; las anteriores las puede inventar el cliente."""
    ajustar(rl_login_ip_min=1, confiar_proxy=True)
    cuerpo = {"email": "admin@hospital-a.co", "password": "ClaveSegura123"}
    h = lambda falsa: {"X-Forwarded-For": f"{falsa}, 203.0.113.50"}  # noqa: E731
    assert (
        await client.post("/api/v1/auth/login", json=cuerpo, headers=h("1.2.3.4"))
    ).status_code == 200
    assert (
        await client.post("/api/v1/auth/login", json=cuerpo, headers=h("5.6.7.8"))
    ).status_code == 429


async def test_limite_general_por_ip_excluye_health_y_metrics(client: AsyncClient, ajustar):
    ajustar(rl_general_ip_min=3)
    for _ in range(3):
        assert (await client.get("/api/v1/expedientes")).status_code == 401  # cuenta
    r = await client.get("/api/v1/expedientes")
    assert r.status_code == 429 and "retry-after" in r.headers
    assert "x-request-id" in r.headers  # incluso el 429 lleva el id para rastrearlo
    # Las sondas de salud y de métricas nunca se limitan.
    assert (await client.get("/health")).status_code == 200
    assert (
        await client.get(
            "/metrics", headers={"Authorization": "Bearer token-de-metricas-de-pruebas"}
        )
    ).status_code == 200


async def test_registro_de_tenants_limitado(client: AsyncClient, ajustar):
    ajustar(rl_registro_ip_hora=2)
    for i in range(2):
        await registrar_org(client, f"90{i}111", f"a{i}@h.co")
    r = await client.post(
        "/api/v1/auth/registro-tenant",
        json={
            "tenant_nombre": "Otra",
            "nit": "999",
            "admin_email": "z@h.co",
            "admin_password": "ClaveSegura123",
            "admin_nombre": "Admin Z",
        },
    )
    assert r.status_code == 429


async def test_consultas_limitadas_por_usuario(client: AsyncClient, app, org_a: Org, ajustar):
    app.dependency_overrides[get_router] = lambda: EmbeddingRouter(
        {"gemini-embedding-001": EmbeddingsFalsos("gemini-embedding-001", 1536)}
    )
    ajustar(rl_consulta_usuario_min=2)
    exp = await org_a.crear_expediente(org_a.admin)
    url = f"/api/v1/expedientes/{exp['id']}/consultas"
    for _ in range(2):
        assert (
            await client.post(url, headers=org_a.admin, json={"pregunta": "¿Plazo?"})
        ).status_code == 200
    r = await client.post(url, headers=org_a.admin, json={"pregunta": "¿Plazo?"})
    assert r.status_code == 429
    # El límite es por usuario: otra persona del mismo tenant sigue pudiendo consultar.
    _, otro = await org_a.crear_usuario("lector@hospital-a.co", "LECTOR")
    uid = (await client.get("/api/v1/auth/me", headers=otro)).json()["id"]
    await client.put(
        f"/api/v1/expedientes/{exp['id']}/permisos/{uid}",
        headers=org_a.admin,
        json={"permiso": "LECTOR"},
    )
    assert (await client.post(url, headers=otro, json={"pregunta": "¿Plazo?"})).status_code == 200


async def test_subidas_limitadas_y_el_rechazo_no_deja_archivos(
    client: AsyncClient, org_a: Org, scanner, cola, ephemeral_dir, ajustar
):
    ajustar(rl_subida_usuario_hora=1)
    exp = await org_a.crear_expediente(org_a.admin)
    assert (await subir(client, org_a.admin, exp["id"], pdf(paginas=1))).status_code == 202
    antes = archivos(ephemeral_dir)
    r = await subir(client, org_a.admin, exp["id"], pdf(paginas=2))
    assert r.status_code == 429
    assert archivos(ephemeral_dir) == antes  # se rechaza antes de aceptar un solo byte


async def test_reindexaciones_limitadas(client: AsyncClient, org_a: Org, ajustar, app, cola):
    app.dependency_overrides[get_router] = lambda: EmbeddingRouter(
        {
            "gemini-embedding-001": EmbeddingsFalsos("gemini-embedding-001", 1536),
            "bge-m3": EmbeddingsFalsos("bge-m3", 1024),
        }
    )
    ajustar(rl_reindex_usuario_hora=1)
    exp = await org_a.crear_expediente(org_a.admin)
    url = f"/api/v1/expedientes/{exp['id']}/reindexaciones"
    assert (
        await client.post(url, headers=org_a.admin, json={"embedding_model": "bge-m3"})
    ).status_code == 202
    assert (
        await client.post(url, headers=org_a.admin, json={"embedding_model": "bge-m3"})
    ).status_code == 429


# ---------- Robustez ----------
class AlmacenRoto:
    async def golpear(self, clave, ventana_s):
        raise ConnectionError("redis caído")

    async def contar(self, clave):
        raise ConnectionError("redis caído")

    async def reiniciar(self):
        return None


async def test_si_redis_cae_el_servicio_sigue_atendiendo(
    client: AsyncClient, org_a: Org, monkeypatch
):
    monkeypatch.setattr(limites, "get_almacen", lambda: AlmacenRoto())
    antes = _valor(LIMITE_FALLOS)
    r = await client.post(
        "/api/v1/auth/login", json={"email": "admin@hospital-a.co", "password": "ClaveSegura123"}
    )
    assert r.status_code == 200
    assert _valor(LIMITE_FALLOS) > antes


async def test_limites_deshabilitados(client: AsyncClient, ajustar):
    ajustar(rate_limit_habilitado=False, rl_general_ip_min=1)
    for _ in range(5):
        assert (await client.get("/api/v1/expedientes")).status_code == 401


def test_clave_de_limite_incluye_regla_ventana_e_identidad():
    ident = str(uuid.uuid4())
    assert limites._clave("consulta_min", ident, 60) == f"rl:consulta_min:60:{ident}"
