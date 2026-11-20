"""Aislamiento por tenant EN la base de datos (RLS, migración V8).

Estas pruebas no pasan por la lógica de la aplicación: consultan directamente con el rol que usa el
agente en producción, para demostrar que PostgreSQL entrega solo las filas del tenant declarado
aunque la consulta no lleve ningún filtro.
"""

import uuid

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.db import _sessionmaker_peticion, fijar_sistema, fijar_tenant, get_sessionmaker
from tests.conftest import Org


async def _codigos(session) -> set[str]:
    filas = await session.execute(text("SELECT codigo_expediente FROM expedientes"))
    return {f[0] for f in filas}


@pytest.fixture
async def dos_orgs(org_a: Org, org_b: Org) -> tuple[Org, Org]:
    await org_a.crear_expediente(codigo="A-001")
    await org_b.crear_expediente(codigo="B-001")
    return org_a, org_b


def test_el_rol_de_la_aplicacion_no_puede_saltarse_rls(postgres_url: str):
    with psycopg.connect(postgres_url) as conn:
        fila = conn.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'medtender_app'"
        ).fetchone()
    assert fila == (False, False)


def test_toda_tabla_con_tenant_id_tiene_rls_forzado(postgres_url: str):
    """Guarda para el futuro: una tabla nueva con tenant_id sin política hace fallar esta prueba."""
    with psycopg.connect(postgres_url) as conn:
        sin_rls = conn.execute(
            """
            SELECT c.relname
            FROM information_schema.columns col
            JOIN pg_class c ON c.relname = col.table_name AND c.relkind = 'r'
            JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = col.table_schema
            WHERE col.table_schema = 'public' AND col.column_name = 'tenant_id'
              AND NOT (c.relrowsecurity AND c.relforcerowsecurity)
            """
        ).fetchall()
    assert sin_rls == [], f"Tablas con tenant_id sin RLS forzado: {sin_rls}"


async def test_sin_contexto_no_se_ve_ninguna_fila(dos_orgs):
    async with _sessionmaker_peticion()() as s:
        assert await _codigos(s) == set()


async def test_cada_tenant_ve_solo_lo_suyo_aunque_la_consulta_no_filtre(dos_orgs):
    org_a, org_b = dos_orgs
    async with _sessionmaker_peticion()() as s:
        fijar_tenant(s, org_a.tenant_id)
        assert await _codigos(s) == {"A-001"}
    async with _sessionmaker_peticion()() as s:
        fijar_tenant(s, org_b.tenant_id)
        assert await _codigos(s) == {"B-001"}


async def test_el_contexto_no_se_filtra_a_la_siguiente_transaccion_del_pool(dos_orgs):
    org_a, _ = dos_orgs
    async with _sessionmaker_peticion()() as s:
        fijar_tenant(s, org_a.tenant_id)
        assert await _codigos(s) == {"A-001"}
    # Una sesión nueva, sin contexto, no hereda al tenant de la anterior aunque reutilice conexión.
    async with _sessionmaker_peticion()() as s:
        assert await _codigos(s) == set()


async def test_el_sistema_ve_todos_los_tenants(dos_orgs):
    async with get_sessionmaker()() as s:
        assert await _codigos(s) == {"A-001", "B-001"}
    async with _sessionmaker_peticion()() as s:
        fijar_sistema(s)
        assert await _codigos(s) == {"A-001", "B-001"}


async def test_no_se_puede_escribir_en_otro_tenant(dos_orgs):
    org_a, org_b = dos_orgs
    async with _sessionmaker_peticion()() as s:
        fijar_tenant(s, org_a.tenant_id)
        with pytest.raises(DBAPIError, match="row-level security"):
            await s.execute(
                text(
                    "INSERT INTO expedientes (id, tenant_id, codigo_expediente, titulo, "
                    "entidad_contratante, tipo_expediente, embedding_model_activo, "
                    "embedding_dimension, created_by) VALUES (:id, :t, 'X-1', 't', 'e', "
                    "'LICITACION_MEDICAMENTOS', 'gemini-embedding-001', 1536, :u)"
                ),
                {"id": uuid.uuid4(), "t": org_b.tenant_id, "u": org_a.admin_id},
            )


async def test_no_se_puede_modificar_ni_borrar_lo_de_otro_tenant(dos_orgs):
    org_a, _ = dos_orgs
    async with _sessionmaker_peticion()() as s:
        fijar_tenant(s, org_a.tenant_id)
        actualizadas = await s.execute(text("UPDATE expedientes SET titulo = 'hackeado'"))
        borradas = await s.execute(text("DELETE FROM expedientes"))
        # Solo alcanza al propio tenant: el expediente B-001 es invisible, no modificable.
        assert actualizadas.rowcount == 1
        assert borradas.rowcount == 1
        await s.rollback()
    async with get_sessionmaker()() as s:
        assert await _codigos(s) == {"A-001", "B-001"}


async def test_tenants_solo_muestra_la_propia_organizacion(dos_orgs):
    org_a, _ = dos_orgs
    async with _sessionmaker_peticion()() as s:
        fijar_tenant(s, org_a.tenant_id)
        ids = {f[0] for f in await s.execute(text("SELECT id FROM tenants"))}
        assert ids == {org_a.tenant_id}
