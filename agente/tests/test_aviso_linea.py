"""El worker le pide al agente que lea el documento recién indexado. Nunca puede dañar la indexación."""

import logging
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.ia.embeddings import EmbeddingRouter, get_router
from app.pipeline.vectorizacion import VectorizadorEmbeddings
from app.services import aviso_linea
from tests.fakes import EmbeddingsFalsos, subir
from tests.pdfs import pdf_texto
from tests.test_cronologia import MODELO, _indexar

AGENTE = "http://agente-de-pruebas:8000"


@pytest.fixture
def router(app):
    r = EmbeddingRouter({MODELO: EmbeddingsFalsos(MODELO, 1536)})
    app.dependency_overrides[get_router] = lambda: r
    return r


@pytest.fixture
def con_agente(monkeypatch):
    monkeypatch.setattr(get_settings(), "agente_url", AGENTE)


async def test_tras_indexar_avisa_al_agente_con_el_token_interno(org_a, router, con_agente):
    expediente = await org_a.crear_expediente()
    doc = await _indexar(expediente, router, "LABORATORIO\n\nGlucosa 91 mg/dL.", "a.pdf")
    with respx.mock as red:
        ruta = red.post(f"{AGENTE}/internal/v1/documentos/{doc}/linea").mock(
            return_value=httpx.Response(200, json={"estado": "extraida"})
        )
        await aviso_linea.pedir_extraccion(get_sessionmaker(), doc)
    [llamada] = ruta.calls
    assert llamada.request.headers["x-internal-token"] == get_settings().internal_token
    assert str(org_a.tenant_id) in llamada.request.content.decode()
    assert expediente["id"] in llamada.request.content.decode()


@pytest.mark.parametrize("fallo", [httpx.ConnectError("caído"), httpx.ReadTimeout("lento")])
async def test_un_agente_caido_no_rompe_nada(org_a, router, con_agente, fallo, caplog):
    expediente = await org_a.crear_expediente()
    doc = await _indexar(expediente, router, "LABORATORIO\n\nGlucosa 91 mg/dL.", "a.pdf")
    with respx.mock as red, caplog.at_level(logging.WARNING, logger="app.services.aviso_linea"):
        red.post(url__startswith=AGENTE).mock(side_effect=fallo)
        await aviso_linea.pedir_extraccion(get_sessionmaker(), doc)
    assert "se leerá al abrir la línea de tiempo" in caplog.text
    assert "Glucosa" not in caplog.text


async def test_un_503_del_agente_tampoco(org_a, router, con_agente):
    expediente = await org_a.crear_expediente()
    doc = await _indexar(expediente, router, "LABORATORIO\n\nGlucosa 91 mg/dL.", "a.pdf")
    with respx.mock as red:
        red.post(url__startswith=AGENTE).mock(return_value=httpx.Response(503))
        await aviso_linea.pedir_extraccion(get_sessionmaker(), doc)


async def test_sin_direccion_del_agente_no_llama(org_a, router, monkeypatch):
    monkeypatch.setattr(get_settings(), "agente_url", "")
    expediente = await org_a.crear_expediente()
    doc = await _indexar(expediente, router, "LABORATORIO\n\nGlucosa 91 mg/dL.", "a.pdf")
    with respx.mock(assert_all_called=False) as red:
        ruta = red.post(url__regex=".*").mock(return_value=httpx.Response(200))
        await aviso_linea.pedir_extraccion(get_sessionmaker(), doc)
    assert not ruta.called


async def test_un_documento_que_no_quedo_indexado_no_se_avisa(org_a, router, con_agente):
    expediente = await org_a.crear_expediente()
    r = await subir(expediente["id"], pdf_texto(["x"]), nombre="en-cola.pdf")
    with respx.mock(assert_all_called=False) as red:
        ruta = red.post(url__regex=".*").mock(return_value=httpx.Response(200))
        await aviso_linea.pedir_extraccion(get_sessionmaker(), r.json()["id"])
    assert not ruta.called


async def test_el_worker_avisa_despues_de_procesar(org_a, router, monkeypatch):
    from app import worker

    avisados = []

    async def anotar(sessionmaker, documento_id):
        avisados.append(documento_id)

    monkeypatch.setattr(worker.aviso_linea, "pedir_extraccion", anotar)
    expediente = await org_a.crear_expediente()
    r = await subir(expediente["id"], pdf_texto(["Glucosa 91 mg/dL."]), nombre="a.pdf")
    with ThreadPoolExecutor(max_workers=1) as ex:
        await worker.procesar_documento(
            {"ejecutor": ex, "vectorizador": VectorizadorEmbeddings(router)}, r.json()["id"]
        )
    assert [str(d) for d in avisados] == [r.json()["id"]]
