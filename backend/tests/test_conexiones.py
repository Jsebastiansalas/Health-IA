"""Ninguna petición debe retener una conexión de base de datos durante una espera larga.

Con un pool de UNA sola conexión, cualquier espera con la conexión tomada (hash de contraseña,
llamada a Gemini, escaneo antivirus) hace que la siguiente petición agote el pool_timeout y falle.
Es el fallo que se observó en la prueba de carga: 30 logins simultáneos agotaban el pool de 15 y
la mitad respondía 500.
"""

import asyncio
import time
import uuid
from contextvars import ContextVar

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core import security
from app.core.config import get_settings
from app.core.db import get_session, get_sessionmaker
from app.core.enums import EstadoIndexacion as E
from app.ia.embeddings import EmbeddingRouter, get_router
from app.ia.llm import RespuestaLLM, get_llm
from app.models import Documento
from app.services.antivirus import ResultadoEscaneo
from app.services.ingesta import validar_y_encolar
from tests.conftest import Org, registrar_org
from tests.fakes import ColaFalsa, EmbeddingsFalsos
from tests.pdfs import pdf
from tests.test_rag import crear_documento, eje

MODELO = "gemini-embedding-001"


@pytest.fixture
async def pool_de_una_conexion():
    engine = create_async_engine(
        get_settings().database_url, pool_size=1, max_overflow=0, pool_timeout=1.5
    )
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def con_pool_chico(app, pool_de_una_conexion):
    async def sesion():
        async with pool_de_una_conexion() as s:
            yield s

    app.dependency_overrides[get_session] = sesion
    return pool_de_una_conexion


def _hash_lento(segundos: float):
    original = security.verify_password

    def lento(password, password_hash):
        time.sleep(segundos)  # se ejecuta en el hilo del ejecutor de bcrypt
        return original(password, password_hash)

    return lento


# ---------- Login ----------
@pytest.mark.parametrize("liberar", [True, False], ids=["libera_la_conexion", "la_retiene"])
async def test_login_no_retiene_la_conexion_durante_el_hash(
    client: AsyncClient, app, monkeypatch, liberar: bool
):
    await registrar_org(client, "900111", "admin@hospital-a.co")
    monkeypatch.setattr(security, "verify_password", _hash_lento(0.5))
    engine = create_async_engine(
        get_settings().database_url, pool_size=1, max_overflow=0, pool_timeout=1.5
    )
    sm = async_sessionmaker(engine, expire_on_commit=False)
    abiertas: list[AsyncSession] = []

    async def sesion():
        async with sm() as s:
            abiertas.append(s)
            yield s

    app.dependency_overrides[get_session] = sesion
    if not liberar:
        # Simula el código anterior: la sesión nunca devuelve la conexión antes del hash.
        async def no_cerrar(self, *a, **k):
            return None

        monkeypatch.setattr(AsyncSession, "close", no_cerrar)

    cuerpo = {"email": "admin@hospital-a.co", "password": "ClaveSegura123"}
    try:
        resultados = await asyncio.gather(
            *[client.post("/api/v1/auth/login", json=cuerpo) for _ in range(6)],
            return_exceptions=True,
        )
    finally:
        monkeypatch.undo()  # restaura AsyncSession.close
        # La variante defectuosa deja conexiones con una transacción abierta; si no se cierran,
        # el TRUNCATE de la limpieza de la base espera su bloqueo indefinidamente.
        for s in abiertas:
            await s.close()
        await engine.dispose()

    codigos = [getattr(r, "status_code", "excepción") for r in resultados]
    if liberar:
        assert codigos == [200] * 6
    else:
        # La variante defectuosa SÍ debe fallar: demuestra que la prueba detecta la regresión.
        assert codigos != [200] * 6


async def test_el_hash_no_congela_el_bucle_de_eventos(client: AsyncClient, monkeypatch):
    await registrar_org(client, "900111", "admin@hospital-a.co")
    monkeypatch.setattr(security, "verify_password", _hash_lento(0.4))
    cuerpo = {"email": "admin@hospital-a.co", "password": "ClaveSegura123"}

    async def ligera():
        """Pasa por el bucle de eventos 20 veces; mide la espera más larga."""
        peor = 0.0
        for _ in range(20):
            t0 = time.perf_counter()
            await asyncio.sleep(0.01)
            peor = max(peor, time.perf_counter() - t0 - 0.01)
        return peor

    logins = [asyncio.create_task(client.post("/api/v1/auth/login", json=cuerpo)) for _ in range(4)]
    peor_espera = await ligera()
    assert [(await t).status_code for t in logins] == [200] * 4
    # Con bcrypt en el bucle, cada login lo congelaba ~0,4 s.
    assert peor_espera < 0.2, f"el bucle de eventos estuvo bloqueado {peor_espera:.2f} s"


async def test_alta_de_usuario_no_retiene_la_conexion(
    client: AsyncClient, org_a: Org, con_pool_chico, monkeypatch
):
    monkeypatch.setattr(security, "hash_password", _hash_lento_hash(0.5))
    resultados = await asyncio.gather(
        *[
            client.post(
                "/api/v1/usuarios",
                headers=org_a.admin,
                json={
                    "email": f"u{i}@hospital-a.co",
                    "password": "ClaveSegura123",
                    "nombre_completo": f"Usuario {i}",
                    "rol_global": "LECTOR",
                },
            )
            for i in range(4)
        ]
    )
    assert [r.status_code for r in resultados] == [201] * 4


def _hash_lento_hash(segundos: float):
    original = security.hash_password

    def lento(password):
        time.sleep(segundos)
        return original(password)

    return lento


# ---------- Consulta RAG ----------
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
    client: AsyncClient, app, org_a: Org, scanner, cola, pool_de_una_conexion
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
    url = f"/api/v1/expedientes/{exp['id']}/consultas"
    respuestas = await asyncio.gather(
        *[
            client.post(url, headers=org_a.admin, json={"pregunta": "¿Cuál es la garantía?"})
            for _ in range(4)
        ]
    )
    assert [r.status_code for r in respuestas] == [200] * 4
    assert all(r.json()["citas"] for r in respuestas)
    assert router.en_transaccion and llm.en_transaccion
    assert not any(router.en_transaccion), "retenía la conexión al llamar a embeddings"
    assert not any(llm.en_transaccion), "retenía la conexión al llamar al modelo generativo"


# ---------- Validación antivirus en segundo plano ----------
async def test_el_escaneo_no_retiene_la_conexion(org_a: Org, pool_de_una_conexion, ephemeral_dir):
    exp = await org_a.crear_expediente(org_a.admin)
    doc_id = uuid.uuid4()
    async with get_sessionmaker()() as s:
        from app.models import Expediente

        expediente = await s.get(Expediente, uuid.UUID(exp["id"]))
        s.add(
            Documento(
                id=doc_id,
                tenant_id=expediente.tenant_id,
                expediente_id=expediente.id,
                nombre_archivo_original="x.pdf",
                tipo_documento="PLIEGO",
                sha256_original="a" * 64,
                tamano_bytes=100,
                estado_indexacion=E.VALIDANDO,
                embedding_model=MODELO,
            )
        )
        await s.commit()
    (ephemeral_dir / f"{doc_id}.pdf").write_bytes(pdf(paginas=2))

    class EscanerQueUsaLaBase:
        async def escanear(self, ruta):
            # Un escaneo real tarda segundos o minutos; aquí, con el pool de UNA conexión, esta
            # consulta solo puede ejecutarse si validar_y_encolar la devolvió antes de escanear.
            async with pool_de_una_conexion() as s:
                await s.execute(text("SELECT 1"))
            return ResultadoEscaneo(limpio=True)

    cola = ColaFalsa()
    await asyncio.wait_for(
        validar_y_encolar(pool_de_una_conexion, doc_id, EscanerQueUsaLaBase(), cola), timeout=5
    )
    async with get_sessionmaker()() as s:
        d = await s.get(Documento, doc_id)
    assert d.estado_indexacion == E.EN_COLA and d.total_paginas == 2
    assert cola.encolados == [doc_id]
