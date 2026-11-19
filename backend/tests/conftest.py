"""Pruebas de integración contra PostgreSQL 16 + pgvector real (Testcontainers).

Requiere Docker en ejecución.
"""

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

# Entorno seguro FIJADO AL IMPORTAR este módulo, antes de que ningún test importe `app`: un test
# que haga `from app.main import ...` construye la configuración en ese momento, y las variables
# de entorno tienen prioridad sobre backend/.env. Así nunca se leen las keys reales ni Redis.
os.environ.update(
    {
        "ENTORNO": "desarrollo",
        "JWT_SECRET": "secreto-de-pruebas-con-longitud-suficiente-1234567890",
        "ALLOW_TENANT_SIGNUP": "true",
        "ANTIVIRUS_BACKEND": "noop",
        "BARRIDO_HABILITADO": "false",
        "COLA_BACKEND": "ninguna",
        "REDIS_URL": "redis://127.0.0.1:1/0",  # inalcanzable a propósito
        "GEMINI_API_KEY": "clave-falsa-de-pruebas",
        "OPENAI_API_KEY": "clave-falsa-de-pruebas",
        "EMBEDDING_MODEL_DEFAULT": "gemini-embedding-001",
        "DB_NULL_POOL": "true",
        # Límites en memoria y muy altos: las pruebas que los verifican los bajan a propósito.
        "RATE_LIMIT_BACKEND": "memoria",
        "METRICS_TOKEN": "token-de-metricas-de-pruebas",
        "RL_GENERAL_IP_MIN": "100000",
        "RL_LOGIN_IP_MIN": "100000",
        "RL_REGISTRO_IP_HORA": "100000",
        "RL_REFRESH_IP_MIN": "100000",
        "RL_CONSULTA_USUARIO_MIN": "100000",
        "RL_CONSULTA_USUARIO_DIA": "100000",
        "RL_SUBIDA_USUARIO_HORA": "100000",
        "RL_REINDEX_USUARIO_HORA": "100000",
    }
)

import psycopg
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from testcontainers.community.postgres import PostgresContainer

from tests.fakes import ColaFalsa, ScannerFalso

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("pgvector/pgvector:pg16", driver=None) as pg:
        yield pg.get_connection_url()  # postgresql://user:pass@host:port/db


@pytest.fixture(scope="session")
def ephemeral_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("medtender-ephemeral")


@pytest.fixture(scope="session", autouse=True)
def _configurar_entorno(postgres_url: str, ephemeral_dir: Path) -> Iterator[None]:
    os.environ["DATABASE_URL"] = postgres_url.replace("postgresql://", "postgresql+asyncpg://")
    os.environ["EPHEMERAL_DIR"] = str(ephemeral_dir)

    # Si algún módulo ya construyó la configuración o el motor antes de conocer la base de
    # datos de pruebas, se descartan.
    from app.core import config, db, limites

    config.get_settings.cache_clear()
    db.get_engine.cache_clear()
    db.get_sessionmaker.cache_clear()
    limites.get_almacen.cache_clear()
    assert config.get_settings().database_url == os.environ["DATABASE_URL"]
    assert config.get_settings().gemini_api_key == "clave-falsa-de-pruebas"

    from alembic.config import Config

    from alembic import command

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _limpiar(postgres_url: str, ephemeral_dir: Path) -> Iterator[None]:
    from app.core import limites

    almacen = limites.get_almacen()
    almacen._datos.clear()  # type: ignore[attr-defined]  # AlmacenMemoria en pruebas
    yield
    with psycopg.connect(postgres_url) as conn:
        conn.execute(
            "TRUNCATE auditoria, actas_purga, consultas, fragmentos, documentos, "
            "expediente_permisos, expedientes, usuarios, tenants RESTART IDENTITY CASCADE"
        )
    for f in ephemeral_dir.iterdir():
        f.unlink()


@pytest.fixture
def app() -> FastAPI:
    from app.main import create_app

    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def scanner(app: FastAPI) -> ScannerFalso:
    from app.services.antivirus import get_scanner

    s = ScannerFalso()
    app.dependency_overrides[get_scanner] = lambda: s
    return s


@pytest.fixture
def cola(app: FastAPI) -> ColaFalsa:
    from app.services.cola import get_cola

    c = ColaFalsa()
    app.dependency_overrides[get_cola] = lambda: c
    return c


class Org:
    """Helper: un tenant con su administrador autenticado."""

    def __init__(self, client: AsyncClient, admin_headers: dict[str, str]):
        self.client = client
        self.admin = admin_headers

    async def crear_usuario(self, email: str, rol: str) -> tuple[str, dict[str, str]]:
        r = await self.client.post(
            "/api/v1/usuarios",
            headers=self.admin,
            json={
                "email": email,
                "password": "ClaveSegura123",
                "nombre_completo": email.split("@")[0],
                "rol_global": rol,
            },
        )
        assert r.status_code == 201, r.text
        login = await self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": "ClaveSegura123"}
        )
        assert login.status_code == 200, login.text
        return r.json()["id"], auth(login.json()["access_token"])

    async def crear_expediente(self, headers: dict[str, str], codigo: str = "LIC-001") -> dict:
        r = await self.client.post(
            "/api/v1/expedientes",
            headers=headers,
            json={
                "codigo_expediente": codigo,
                "titulo": "Suministro de medicamentos oncológicos",
                "entidad_contratante": "Hospital Universitario",
                "tipo_expediente": "LICITACION_MEDICAMENTOS",
            },
        )
        assert r.status_code == 201, r.text
        return r.json()


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def registrar_org(client: AsyncClient, nit: str, email: str) -> Org:
    r = await client.post(
        "/api/v1/auth/registro-tenant",
        json={
            "tenant_nombre": f"Hospital {nit}",
            "nit": nit,
            "admin_email": email,
            "admin_password": "ClaveSegura123",
            "admin_nombre": "Admin",
        },
    )
    assert r.status_code == 201, r.text
    return Org(client, auth(r.json()["access_token"]))


@pytest.fixture
async def org_a(client: AsyncClient) -> Org:
    return await registrar_org(client, "900111", "admin@hospital-a.co")


@pytest.fixture
async def org_b(client: AsyncClient) -> Org:
    return await registrar_org(client, "900222", "admin@clinica-b.co")
