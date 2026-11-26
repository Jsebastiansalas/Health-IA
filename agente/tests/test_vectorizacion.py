"""Vectorización, purga final y re-vectorización sin PDF contra PostgreSQL + pgvector real."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select, text, update

from app.core.db import get_sessionmaker
from app.core.enums import EstadoIndexacion as E
from app.ia.embeddings import EmbeddingRouter, a_columna, get_router
from app.models import ActaPurga, Documento, Expediente, Fragmento, Reindexacion
from app.pipeline.procesador import procesar_documento
from app.pipeline.vectorizacion import VectorizadorEmbeddings
from app.services import reindexacion
from tests.fakes import EmbeddingsFalsos, archivos, subir
from tests.pdfs import pdf_tabla, pdf_texto, texto_largo, unir


@pytest.fixture
def proveedores():
    return {
        "gemini-embedding-001": EmbeddingsFalsos("gemini-embedding-001", 1536),
        "bge-m3": EmbeddingsFalsos("bge-m3", 1024),
    }


@pytest.fixture
def router(app, proveedores) -> EmbeddingRouter:
    r = EmbeddingRouter(proveedores)
    app.dependency_overrides[get_router] = lambda: r
    return r


@pytest.fixture
def ejecutor():
    with ThreadPoolExecutor(max_workers=1) as ex:
        yield ex


@pytest.fixture
async def expediente(org_a, cola):
    return await org_a.crear_expediente(org_a.admin)


def pliego(sufijo: str = "") -> bytes:
    return unir(
        pdf_texto(
            [
                "CAPÍTULO 1 OBJETO\n\n" + texto_largo(30) + sufijo,
                "CLÁUSULA 5 GARANTÍAS\n\n" + texto_largo(30, tema="garantías"),
            ]
        ),
        pdf_tabla(
            "CUADRO DE PRECIOS",
            [["Código CUM", "Principio activo"], ["19912345-1", "Paclitaxel"]],
        ),
    )


async def indexar(client, org_a, expediente, ejecutor, router, contenido=None) -> uuid.UUID:
    r = await subir(expediente["id"], contenido or pliego())
    doc_id = uuid.UUID(r.json()["id"])
    await procesar_documento(get_sessionmaker(), doc_id, ejecutor, VectorizadorEmbeddings(router))
    return doc_id


async def _cargar(doc_id):
    async with get_sessionmaker()() as s:
        d = await s.get(Documento, doc_id)
        frags = list(
            await s.scalars(
                select(Fragmento).where(Fragmento.documento_id == doc_id).order_by(Fragmento.orden)
            )
        )
        actas = list(await s.scalars(select(ActaPurga).where(ActaPurga.documento_id == doc_id)))
        return d, frags, actas


# ---------- Pasos 7, 8 y 9 ----------
async def test_indexacion_completa_y_purga(
    client, org_a, expediente, ejecutor, router, proveedores, ephemeral_dir
):
    doc_id = await indexar(client, org_a, expediente, ejecutor, router)

    d, frags, actas = await _cargar(doc_id)
    assert d.estado_indexacion == E.INDEXADO_Y_PURGADO
    assert d.temp_file_purged and d.purged_at is not None
    assert d.total_chunks_guardados == d.total_chunks_esperados == len(frags) > 0
    assert archivos(ephemeral_dir) == []  # Paso 9: el PDF ya no está en el servidor
    assert [(a.motivo, a.chunks_esperados, a.chunks_verificados) for a in actas] == [
        ("INDEXADO", len(frags), len(frags))
    ]
    for f in frags:
        assert f.embedding is not None and len(f.embedding) == 1536
        assert f.embedding_model == "gemini-embedding-001"
    # Se vectorizó contenido_vectorizado (con cabecera), como documento y no como consulta.
    assert {t for t, _ in proveedores["gemini-embedding-001"].llamadas} == {"documento"}


async def test_politica_diferida_deja_el_pdf_una_hora(
    client, org_a, expediente, ejecutor, router, ephemeral_dir
):
    org_a.politica_de_borrado("DIFERIDO_1H")
    doc_id = await indexar(client, org_a, expediente, ejecutor, router)
    d, _, _ = await _cargar(doc_id)
    assert d.estado_indexacion == E.INDEXADO_PENDIENTE_PURGA
    assert archivos(ephemeral_dir) == [f"{doc_id}.pdf"]


async def test_fallo_del_proveedor_purga_y_no_deja_indice_parcial(
    client, org_a, expediente, ejecutor, proveedores, ephemeral_dir
):
    proveedores["gemini-embedding-001"].falla_en_llamada = 1
    doc_id = await indexar(client, org_a, expediente, ejecutor, EmbeddingRouter(proveedores))
    d, frags, actas = await _cargar(doc_id)
    assert d.estado_indexacion == E.ERROR_PURGADO
    assert "no responde" in d.motivo_error
    assert frags == []
    assert archivos(ephemeral_dir) == []
    assert [a.motivo for a in actas] == ["ERROR_PROCESAMIENTO"]


async def test_usa_el_modelo_vigente_del_expediente(
    client, org_a, expediente, ejecutor, router, proveedores
):
    r = await subir(expediente["id"], pliego())
    doc_id = uuid.UUID(r.json()["id"])
    # El expediente cambió de modelo mientras el documento esperaba en la cola.
    async with get_sessionmaker()() as s:
        await s.execute(
            update(Expediente)
            .where(Expediente.id == uuid.UUID(expediente["id"]))
            .values(embedding_model_activo="bge-m3", embedding_dimension=1024)
        )
        await s.commit()
    await procesar_documento(get_sessionmaker(), doc_id, ejecutor, VectorizadorEmbeddings(router))

    d, frags, _ = await _cargar(doc_id)
    assert d.estado_indexacion == E.INDEXADO_Y_PURGADO
    assert d.embedding_model == "bge-m3"
    assert all(
        f.embedding_model == "bge-m3" and list(f.embedding[1024:]) == [0.0] * 512 for f in frags
    )
    assert proveedores["gemini-embedding-001"].llamadas == []


async def test_busqueda_vectorial_con_el_mismo_modelo(client, org_a, expediente, ejecutor, router):
    """Paso 11-12 (adelanto del Sprint 5): la consulta se vectoriza con el modelo del índice."""
    doc_id = await indexar(client, org_a, expediente, ejecutor, router)
    _, frags, _ = await _cargar(doc_id)
    objetivo = frags[-1]

    vector = await router.embeber_consulta("gemini-embedding-001", objetivo.contenido_vectorizado)
    async with get_sessionmaker()() as s:
        top = await s.scalar(
            select(Fragmento.id)
            .where(
                Fragmento.tenant_id == objetivo.tenant_id,
                Fragmento.expediente_id == objetivo.expediente_id,
            )
            .order_by(Fragmento.embedding.cosine_distance(a_columna(vector)))
            .limit(1)
        )
    assert top == objetivo.id


# ---------- HU4.4: re-vectorización sin PDF ----------
async def _reindexar(client, org, expediente, modelo="bge-m3"):
    return await client.post(
        "/internal/v1/reindexaciones",
        headers=org.admin,
        json={
            "tenant_id": str(org.tenant_id),
            "expediente_id": expediente["id"],
            "usuario_id": str(org.admin_id),
            "embedding_model": modelo,
        },
    )


async def test_reindexacion_a_modelo_local_sin_pdf(
    client, org_a, expediente, ejecutor, router, cola, ephemeral_dir
):
    doc_id = await indexar(client, org_a, expediente, ejecutor, router)
    _, antes, _ = await _cargar(doc_id)
    assert archivos(ephemeral_dir) == []  # el PDF ya fue purgado

    r = await _reindexar(client, org_a, expediente)
    assert r.status_code == 202, r.text
    rid = uuid.UUID(r.json()["id"])
    assert r.json()["estado"] == "PENDIENTE"
    assert r.json()["total_fragmentos"] == len(antes)
    assert cola.reindexaciones == [rid]

    await reindexacion.ejecutar(get_sessionmaker(), rid, router)

    d, despues, _ = await _cargar(doc_id)
    async with get_sessionmaker()() as s:
        exp = await s.get(Expediente, uuid.UUID(expediente["id"]))
        rx = await s.get(Reindexacion, rid)
        preparados = await s.scalar(text("SELECT COUNT(*) FROM fragmentos_reindex"))
    assert rx.estado == "COMPLETADA" and rx.fragmentos_procesados == len(antes)
    assert (exp.embedding_model_activo, exp.embedding_dimension) == ("bge-m3", 1024)
    assert d.embedding_model == "bge-m3"
    assert preparados == 0
    for a, b in zip(antes, despues, strict=True):
        assert b.id == a.id and b.contenido_texto == a.contenido_texto  # mismo texto, sin PDF
        assert b.embedding_model == "bge-m3"
        assert list(b.embedding[1024:]) == [0.0] * 512
        assert list(b.embedding) != list(a.embedding)

    lista = await client.get(
        "/internal/v1/reindexaciones",
        headers=org_a.admin,
        params={"tenant_id": str(org_a.tenant_id), "expediente_id": expediente["id"]},
    )
    assert [x["estado"] for x in lista.json()] == ["COMPLETADA"]


async def test_reindexacion_fallida_conserva_el_indice_original(
    client, org_a, expediente, ejecutor, router, proveedores
):
    doc_id = await indexar(client, org_a, expediente, ejecutor, router)
    _, antes, _ = await _cargar(doc_id)
    proveedores["bge-m3"].falla_en_llamada = 1

    rid = uuid.UUID((await _reindexar(client, org_a, expediente)).json()["id"])
    await reindexacion.ejecutar(get_sessionmaker(), rid, router)

    d, despues, _ = await _cargar(doc_id)
    async with get_sessionmaker()() as s:
        exp = await s.get(Expediente, uuid.UUID(expediente["id"]))
        rx = await s.get(Reindexacion, rid)
        preparados = await s.scalar(text("SELECT COUNT(*) FROM fragmentos_reindex"))
    assert rx.estado == "ERROR" and "no responde" in rx.error
    assert exp.embedding_model_activo == "gemini-embedding-001"
    assert [list(f.embedding) for f in despues] == [list(f.embedding) for f in antes]
    assert preparados == 0
    # Se puede volver a intentar.
    proveedores["bge-m3"].falla_en_llamada = None
    assert (await _reindexar(client, org_a, expediente)).status_code == 202


async def test_validaciones_de_reindexacion(client, org_a, expediente, ejecutor, router):
    await indexar(client, org_a, expediente, ejecutor, router)

    assert (await _reindexar(client, org_a, expediente, "gemini-embedding-001")).status_code == 409
    assert (await _reindexar(client, org_a, expediente, "modelo-inventado")).status_code == 422

    assert (await _reindexar(client, org_a, expediente)).status_code == 202
    # Solo una activa a la vez (que no se acepten subidas mientras tanto lo vigila la API Java).
    assert (await _reindexar(client, org_a, expediente)).status_code == 409


async def test_no_se_reindexa_con_documentos_en_proceso(client, org_a, expediente, router):
    await subir(expediente["id"], pliego())  # queda EN_COLA
    r = await _reindexar(client, org_a, expediente)
    assert r.status_code == 409 and "en procesamiento" in r.json()["detail"]


async def test_otro_tenant_no_puede_reindexar(client, org_a, org_b, expediente, router):
    # El tenant va en la solicitud: un expediente que no es de ese tenant no existe para el agente.
    assert (await _reindexar(client, org_b, expediente)).status_code == 404


async def test_lista_de_modelos(client, org_a, router):
    r = await client.get("/internal/v1/embeddings/modelos", headers=org_a.admin)
    assert {m["modelo"]: m["dimension"] for m in r.json()} == {
        "gemini-embedding-001": 1536,
        "bge-m3": 1024,
    }


async def test_conteo_de_fragmentos_por_tenant(client, org_a, org_b, ejecutor, router, cola):
    """Los fragmentos llevan tenant_id y expediente_id para el filtro obligatorio del Paso 12."""
    exp_a = await org_a.crear_expediente(org_a.admin, "A-1")
    exp_b = await org_b.crear_expediente(org_b.admin, "B-1")
    await indexar(client, org_a, exp_a, ejecutor, router)
    await indexar(client, org_b, exp_b, ejecutor, router, pliego(" B"))
    async with get_sessionmaker()() as s:
        por_tenant = (
            await s.execute(select(Fragmento.tenant_id, func.count()).group_by(Fragmento.tenant_id))
        ).all()
    assert len(por_tenant) == 2
