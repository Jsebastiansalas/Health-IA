"""Pruebas de integración contra PostgreSQL 16 + pgvector real (Testcontainers).

Requiere Docker en ejecución. El esquema NO se define aquí: es el de Flyway (api-java), que se
aplica tal cual, de modo que el agente se prueba contra la misma base que verá en producción.
"""

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

# Entorno seguro FIJADO AL IMPORTAR este módulo, antes de que ningún test importe `app`: un test
# que haga `from app.main import ...` construye la configuración en ese momento, y las variables
# de entorno tienen prioridad sobre backend/.env. Así nunca se leen las keys reales ni Redis.
os.environ.update(
    {
        "ENTORNO": "desarrollo",
        "INTERNAL_TOKEN": "token-interno-de-pruebas-con-longitud-suficiente-123456",
        "BARRIDO_HABILITADO": "false",
        "COLA_BACKEND": "ninguna",
        "REDIS_URL": "redis://127.0.0.1:1/0",  # inalcanzable a propósito
        "GEMINI_API_KEY": "clave-falsa-de-pruebas",
        "OPENAI_API_KEY": "clave-falsa-de-pruebas",
        "EMBEDDING_MODEL_DEFAULT": "gemini-embedding-001",
        "DB_NULL_POOL": "true",
        "METRICS_TOKEN": "token-de-metricas-de-pruebas",
    }
)

import psycopg
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from testcontainers.community.postgres import PostgresContainer

from tests.fakes import ColaFalsa

TOKEN_INTERNO = os.environ["INTERNAL_TOKEN"]
APP_PASSWORD = "contrasena-app-de-pruebas"
RAIZ = Path(__file__).resolve().parents[2]
MIGRACIONES = RAIZ / "api-java" / "src" / "main" / "resources" / "db" / "migration"


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("pgvector/pgvector:pg16", driver=None) as pg:
        yield pg.get_connection_url()  # postgresql://user:pass@host:port/db


@pytest.fixture(scope="session")
def ephemeral_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("medtender-ephemeral")


@pytest.fixture(scope="session", autouse=True)
def _configurar_entorno(postgres_url: str, ephemeral_dir: Path) -> Iterator[None]:
    # El agente se conecta con el rol de aplicación que crea V8 (sin superusuario): así las
    # políticas de aislamiento por tenant (RLS) están en vigor durante las pruebas.
    # `postgres_url` (propietario) solo prepara y limpia datos.
    app_url = postgres_url.replace("postgresql://", "postgresql+asyncpg://")
    app_url = app_url.replace(app_url.split("//")[1].split("@")[0], f"medtender_app:{APP_PASSWORD}")
    os.environ["DATABASE_URL"] = app_url
    os.environ["TEST_DATABASE_ADMIN_URL"] = postgres_url  # propietario: ignora RLS
    os.environ["EPHEMERAL_DIR"] = str(ephemeral_dir)

    # Si algún módulo ya construyó la configuración o el motor antes de conocer la base de
    # datos de pruebas, se descartan.
    from app.core import config, db

    config.get_settings.cache_clear()
    db.get_engine.cache_clear()
    db.get_sessionmaker.cache_clear()
    assert config.get_settings().database_url == os.environ["DATABASE_URL"]
    assert config.get_settings().gemini_api_key == "clave-falsa-de-pruebas"

    # Esquema: los mismos V1..V6 que aplica Flyway (orden numérico, no alfabético).
    scripts = sorted(MIGRACIONES.glob("V*__*.sql"), key=lambda p: int(p.name[1:].split("__")[0]))
    assert len(scripts) >= 8, f"No se encontraron las migraciones de Flyway en {MIGRACIONES}"
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        for script in scripts:
            conn.execute(script.read_text(encoding="utf-8").replace("${app_password}", APP_PASSWORD))
    yield


@pytest.fixture(autouse=True)
def _limpiar(postgres_url: str, ephemeral_dir: Path) -> Iterator[None]:
    yield
    with psycopg.connect(postgres_url) as conn:
        conn.execute(
            "TRUNCATE auditoria, actas_purga, consultas, fragmentos, documentos, "
            "expediente_permisos, expedientes, usuarios, tenants, med_cum, med_precio, med_carga "
            "RESTART IDENTITY CASCADE"
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
def cola(app: FastAPI) -> ColaFalsa:
    from app.services.cola import get_cola

    c = ColaFalsa()
    app.dependency_overrides[get_cola] = lambda: c
    return c


def interno() -> dict[str, str]:
    """Cabecera con la que la API Java se identifica ante el agente."""
    return {"X-Internal-Token": TOKEN_INTERNO}


class Org:
    """Un tenant con su administrador, creados directamente en la base (como haría la API Java).

    `admin` es la cabecera interna: el agente no autentica usuarios, así que cualquiera de los
    usuarios de la organización "habla" con el mismo token; lo que cambia es el `usuario_id` del
    cuerpo de cada solicitud.
    """

    def __init__(self, postgres_url: str, nit: str, email: str):
        self.postgres_url = postgres_url
        self.tenant_id = uuid.uuid4()
        self.admin_id = uuid.uuid4()
        self.admin = interno()
        with psycopg.connect(postgres_url) as conn:
            conn.execute(
                "INSERT INTO tenants (id, nombre, nit) VALUES (%s, %s, %s)",
                (self.tenant_id, f"Hospital {nit}", nit),
            )
            self._insertar_usuario(conn, self.admin_id, email, "ADMIN_TENANT")

    def _insertar_usuario(self, conn, uid: uuid.UUID, email: str, rol: str) -> None:
        conn.execute(
            "INSERT INTO usuarios (id, tenant_id, email, password_hash, nombre_completo, rol_global) "
            "VALUES (%s, %s, %s, 'hash-de-prueba', %s, %s)",
            (uid, self.tenant_id, email, email.split("@")[0], rol),
        )

    async def crear_usuario(self, email: str, rol: str) -> tuple[str, dict[str, str]]:
        uid = uuid.uuid4()
        with psycopg.connect(self.postgres_url) as conn:
            self._insertar_usuario(conn, uid, email, rol)
        return str(uid), self.admin

    async def crear_expediente(self, headers: dict | None = None, codigo: str = "LIC-001") -> dict:
        eid = uuid.uuid4()
        with psycopg.connect(self.postgres_url) as conn:
            conn.execute(
                "INSERT INTO expedientes (id, tenant_id, codigo_expediente, titulo, "
                "entidad_contratante, tipo_expediente, embedding_model_activo, embedding_dimension, "
                "created_by) VALUES (%s, %s, %s, 'Suministro de medicamentos oncológicos', "
                "'Hospital Universitario', 'LICITACION_MEDICAMENTOS', 'gemini-embedding-001', "
                "1536, %s)",
                (eid, self.tenant_id, codigo, self.admin_id),
            )
        return {
            "id": str(eid),
            "tenant_id": str(self.tenant_id),
            "codigo_expediente": codigo,
            "embedding_model_activo": "gemini-embedding-001",
        }

    def politica_de_borrado(self, politica: str) -> None:
        with psycopg.connect(self.postgres_url) as conn:
            conn.execute(
                "UPDATE tenants SET politica_borrado = %s WHERE id = %s", (politica, self.tenant_id)
            )


@pytest.fixture
def org_a(postgres_url: str) -> Org:
    return Org(postgres_url, "900111", "admin@hospital-a.co")


@pytest.fixture
def org_b(postgres_url: str) -> Org:
    return Org(postgres_url, "900222", "admin@clinica-b.co")
