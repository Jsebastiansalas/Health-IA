"""Ninguna petición debe retener una conexión de base de datos durante una espera larga.

Con un pool de UNA sola conexión, cualquier espera con la conexión tomada (llamada a Gemini o al
modelo generativo) hace que la siguiente petición agote el pool_timeout y falle. (Los hashes de
contraseña y el escaneo antivirus, que originaron esta prueba, ahora son de la API Java.)
"""

import asyncio
import uuid
from contextvars import ContextVar

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.db import get_session, get_sessionmaker
from app.ia.embeddings import EmbeddingRouter, get_router
from app.ia.llm import RespuestaLLM, get_llm
from tests.conftest import Org
from tests.fakes import EmbeddingsFalsos
from tests.test_rag import crear_documento, eje

MODELO = "gemini-embedding-001"


@pytest.fixture
async def pool_de_una_conexion():
    engine = create_async_engine(
        get_settings().database_url, pool_size=1, max_overflow=0, pool_timeout=1.5
    )
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


# La sesión de la petición en curso: cada petición corre en su propia tarea, así que la variable
# de contexto distingue la sesión de quien llama de las de las demás peticiones simultáneas.
sesion_actual: ContextVar[AsyncSession] = ContextVar("sesion_actual")


class RouterQueVigila(EmbeddingsFalsos):
    def __init__(self):
        super().__init__(MODELO, 1536)
        self.en_transaccion: list[bool] = []

    async def embeber(self, textos, tarea):
        self.en_transaccion.append(sesion_actual.get().in_transaction())
        await asyncio.sleep(0.4)
        return await super().embeber(textos, tarea)


class LLMQueVigila:
    modelo = "gemini-falso"

    def __init__(self):
        self.en_transaccion: list[bool] = []

    async def generar_json(self, sistema, prompt, esquema):
        self.en_transaccion.append(sesion_actual.get().in_transaction())
        await asyncio.sleep(0.6)
        return RespuestaLLM(
            {
                "respuesta": "Garantía de doce meses.",
                "hay_evidencia": True,
                "citas": [{"fragmento": "F1", "extracto_literal": "garantía"}],
                "alertas": [],
            },
            self.modelo,
        )


async def test_la_consulta_suelta_la_conexion_mientras_espera_a_gemini(
    client: AsyncClient, app, org_a: Org, cola, pool_de_una_conexion
):
    async def sesion():
        async with pool_de_una_conexion() as s:
            sesion_actual.set(s)
            yield s

    app.dependency_overrides[get_session] = sesion
    router = RouterQueVigila()
    llm = LLMQueVigila()
    app.dependency_overrides[get_router] = lambda: EmbeddingRouter({MODELO: router})
    app.dependency_overrides[get_llm] = lambda: llm

    exp = await org_a.crear_expediente(org_a.admin)
    async with get_sessionmaker()() as s:
        from app.models import Expediente

        expediente = await s.get(Expediente, uuid.UUID(exp["id"]))
    await crear_documento(expediente, [("La garantía mínima es de doce meses.", eje(1))])

    # Cuatro consultas a la vez contra un pool de una conexión: si alguna retuviera la conexión
    # mientras espera a Gemini, las demás agotarían el pool_timeout de 1,5 s.
    cuerpo = {
        "tenant_id": exp["tenant_id"],
        "expediente_id": exp["id"],
        "usuario_id": str(org_a.admin_id),
        "pregunta": "¿Cuál es la garantía?",
    }
    respuestas = await asyncio.gather(
        *[client.post("/internal/v1/consultas", headers=org_a.admin, json=cuerpo) for _ in range(4)]
    )
    assert [r.status_code for r in respuestas] == [200] * 4
    assert all(r.json()["citas"] for r in respuestas)
    assert router.en_transaccion and llm.en_transaccion
    assert not any(router.en_transaccion), "retenía la conexión al llamar a embeddings"
    assert not any(llm.en_transaccion), "retenía la conexión al llamar al modelo generativo"
