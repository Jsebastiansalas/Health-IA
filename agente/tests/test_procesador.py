"""Pipeline completo del worker contra PostgreSQL real: EN_COLA -> ... -> VECTORIZANDO."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from app.core.db import get_sessionmaker
from app.core.enums import EstadoIndexacion as E
from app.models import ActaPurga, Documento, Fragmento
from app.pipeline.procesador import procesar_documento
from app.services.estados import transicionar
from tests.fakes import archivos, subir
from tests.pdfs import pdf, pdf_con_sello, pdf_tabla, pdf_texto, texto_largo, unir


class VectorizadorFalso:
    def __init__(self, falla: bool = False):
        self.falla = falla
        self.llamadas: list[uuid.UUID] = []

    async def vectorizar(self, sessionmaker, documento_id):
        self.llamadas.append(documento_id)
        if self.falla:
            raise RuntimeError("OpenAI no responde")


@pytest.fixture
def ejecutor():
    # Un solo hilo: pdfium no es seguro entre hilos (en producción se usan procesos).
    with ThreadPoolExecutor(max_workers=1) as ex:
        yield ex


@pytest.fixture
async def expediente(org_a, cola):
    return await org_a.crear_expediente(org_a.admin)


def pliego() -> bytes:
    filas = [
        ["Código CUM", "Principio activo", "Precio"],
        ["19912345-1", "Paclitaxel", "$ 125.000"],
    ]
    return unir(
        pdf_texto(
            [
                "CAPÍTULO 1 OBJETO\n\n" + texto_largo(30),
                texto_largo(30, tema="lote 2"),
                "CLÁUSULA 5 GARANTÍAS\n\n" + texto_largo(30, tema="garantías"),
            ]
        ),
        pdf_tabla("CUADRO DE PRECIOS", filas),
        pdf_con_sello("Certificación expedida y firmada por el representante legal."),
    )


async def _subir(client, org_a, expediente, contenido: bytes) -> uuid.UUID:
    r = await subir(expediente["id"], contenido)
    assert r.status_code == 202, r.text
    return uuid.UUID(r.json()["id"])


async def _documento(doc_id) -> tuple[Documento, list[Fragmento]]:
    async with get_sessionmaker()() as s:
        d = await s.get(Documento, doc_id)
        frags = list(
            await s.scalars(
                select(Fragmento).where(Fragmento.documento_id == doc_id).order_by(Fragmento.orden)
            )
        )
        return d, frags


async def test_pipeline_completo(client, org_a, expediente, ejecutor, ephemeral_dir):
    doc_id = await _subir(client, org_a, expediente, pliego())
    vectorizador = VectorizadorFalso()

    await procesar_documento(get_sessionmaker(), doc_id, ejecutor, vectorizador)

    d, frags = await _documento(doc_id)
    assert d.estado_indexacion == E.VECTORIZANDO
    assert d.total_paginas == 5
    assert d.extractor_version == "pdfium-pdfplumber-v1"
    assert d.total_chunks_esperados == len(frags) > 0
    assert vectorizador.llamadas == [doc_id]
    # El PDF sigue en disco: se purga tras verificar la vectorización (Sprint 4).
    assert archivos(ephemeral_dir) == [f"{doc_id}.pdf"]

    assert [f.orden for f in frags] == list(range(1, len(frags) + 1))
    for f in frags:
        assert f.embedding is None
        assert f.tenant_id == d.tenant_id and f.expediente_id == d.expediente_id
        assert f.token_count <= 1000
        assert f.embedding_model == "gemini-embedding-001"
        # Con la anonimización activa (por defecto) el nombre del archivo no sale a la nube: suele traer
        # el nombre de una persona. El nombre real se conserva en `documentos`.
        assert f.contenido_vectorizado.startswith(
            f"[Expediente: LIC-001 | Doc: documento | Tipo: PLIEGO | "
            f"Pág: {f.pagina_inicio}-{f.pagina_fin} | Sección: {f.seccion}] "
        )
        assert f.metadata_jsonb["tipo_documento"] == "PLIEGO"
        assert f.metadata_jsonb["numero_adenda"] == 0
        assert f.metadata_jsonb["extraction_method"] == "NATIVE"

    assert frags[0].seccion == "CAPÍTULO 1 OBJETO"
    # Regresión: líneas de texto corrido ("ficha técnica del equipo 24...") no son secciones.
    secciones_vistas = {s for f in frags for s in f.seccion.split(" / ")}
    assert secciones_vistas <= {"CAPÍTULO 1 OBJETO", "CLÁUSULA 5 GARANTÍAS"}
    assert any("CLÁUSULA 5 GARANTÍAS" in f.seccion for f in frags)
    tabla = next(f for f in frags if f.metadata_jsonb["has_tables"])
    assert "| 19912345-1 | Paclitaxel | $ 125.000 |" in tabla.contenido_texto
    ultimo = frags[-1]
    assert ultimo.pagina_fin == 5
    assert ultimo.metadata_jsonb["has_signatures_or_stamps"] is True


async def test_busqueda_textual_ya_funciona_sobre_fragmentos(client, org_a, expediente, ejecutor):
    """La columna fts_vector (GENERATED, diccionario 'spanish') se calcula al insertar."""
    doc_id = await _subir(client, org_a, expediente, pliego())
    await procesar_documento(get_sessionmaker(), doc_id, ejecutor, VectorizadorFalso())
    async with get_sessionmaker()() as s:
        n = await s.scalar(
            select(func.count())
            .select_from(Fragmento)
            .where(
                Fragmento.documento_id == doc_id,
                Fragmento.fts_vector.op("@@")(func.websearch_to_tsquery("spanish", "paclitaxel")),
            )
        )
    assert n == 1


async def test_pdf_sin_texto_termina_en_error_purgado(
    client, org_a, expediente, ejecutor, ephemeral_dir
):
    doc_id = await _subir(client, org_a, expediente, pdf(paginas=2))
    vectorizador = VectorizadorFalso()
    await procesar_documento(get_sessionmaker(), doc_id, ejecutor, vectorizador)

    d, frags = await _documento(doc_id)
    assert d.estado_indexacion == E.ERROR_PURGADO
    assert "No se pudo extraer texto" in d.motivo_error
    assert frags == [] and vectorizador.llamadas == []
    assert archivos(ephemeral_dir) == []


async def test_archivo_temporal_ausente(client, org_a, expediente, ejecutor, ephemeral_dir):
    doc_id = await _subir(client, org_a, expediente, pdf_texto(["Texto suficiente " * 10]))
    (ephemeral_dir / f"{doc_id}.pdf").unlink()
    await procesar_documento(get_sessionmaker(), doc_id, ejecutor, VectorizadorFalso())
    d, _ = await _documento(doc_id)
    assert d.estado_indexacion == E.ERROR_PURGADO
    assert "ArchivoTemporalAusente" in d.motivo_error


async def test_archivo_danado_despues_de_validar(
    client, org_a, expediente, ejecutor, ephemeral_dir
):
    doc_id = await _subir(client, org_a, expediente, pdf_texto(["Texto suficiente " * 10]))
    (ephemeral_dir / f"{doc_id}.pdf").write_bytes(b"%PDF-1.7 corrupto")
    await procesar_documento(get_sessionmaker(), doc_id, ejecutor, VectorizadorFalso())
    d, _ = await _documento(doc_id)
    assert d.estado_indexacion == E.ERROR_PURGADO
    assert archivos(ephemeral_dir) == []


async def test_fallo_en_vectorizacion_purga_y_borra_fragmentos(
    client, org_a, expediente, ejecutor, ephemeral_dir
):
    doc_id = await _subir(client, org_a, expediente, pliego())
    await procesar_documento(get_sessionmaker(), doc_id, ejecutor, VectorizadorFalso(falla=True))

    d, frags = await _documento(doc_id)
    assert d.estado_indexacion == E.ERROR_PURGADO
    assert "OpenAI no responde" in d.motivo_error
    assert frags == []  # un índice parcial no queda consultable
    assert archivos(ephemeral_dir) == []
    async with get_sessionmaker()() as s:
        motivos = list(
            await s.scalars(select(ActaPurga.motivo).where(ActaPurga.documento_id == doc_id))
        )
    assert motivos == ["ERROR_PROCESAMIENTO"]


async def test_es_idempotente(client, org_a, expediente, ejecutor):
    doc_id = await _subir(client, org_a, expediente, pliego())
    vectorizador = VectorizadorFalso()
    await procesar_documento(get_sessionmaker(), doc_id, ejecutor, vectorizador)
    _, antes = await _documento(doc_id)

    # Un trabajo duplicado no reprocesa ni duplica fragmentos.
    await procesar_documento(get_sessionmaker(), doc_id, ejecutor, vectorizador)
    d, despues = await _documento(doc_id)
    assert d.estado_indexacion == E.VECTORIZANDO
    assert len(despues) == len(antes)
    assert vectorizador.llamadas == [doc_id]


async def test_reintento_tras_caida_del_worker(client, org_a, expediente, ejecutor):
    doc_id = await _subir(client, org_a, expediente, pliego())
    # Simula una caída a mitad de la fragmentación, con un fragmento huérfano ya escrito.
    async with get_sessionmaker()() as s:
        d = await s.get(Documento, doc_id)
        transicionar(d, E.EXTRAYENDO_OCR)
        transicionar(d, E.FRAGMENTANDO)
        s.add(
            Fragmento(
                tenant_id=d.tenant_id,
                expediente_id=d.expediente_id,
                documento_id=d.id,
                orden=1,
                pagina_inicio=1,
                pagina_fin=1,
                seccion="x",
                contenido_texto="parcial",
                contenido_vectorizado="parcial",
                token_count=1,
                embedding_model="m",
            )
        )
        await s.commit()

    # Primer intento: no toca un documento ajeno a EN_COLA.
    await procesar_documento(get_sessionmaker(), doc_id, ejecutor, VectorizadorFalso())
    assert (await _documento(doc_id))[0].estado_indexacion == E.FRAGMENTANDO

    # Reintento de ARQ (job_try=2): limpia y reprocesa.
    await procesar_documento(get_sessionmaker(), doc_id, ejecutor, VectorizadorFalso(), intento=2)
    d, frags = await _documento(doc_id)
    assert d.estado_indexacion == E.VECTORIZANDO
    assert d.total_chunks_esperados == len(frags)
    assert "parcial" not in [f.contenido_texto for f in frags]


async def test_numero_de_adenda_en_metadata(client, org_a, expediente, ejecutor):
    r = await subir(
        expediente["id"],
        pdf_texto(["ADENDA No. 2\n\n" + texto_largo(10)]),
        tipo="ADENDA",
        numero_adenda=2,
        nombre="Adenda_02.pdf",
    )
    doc_id = uuid.UUID(r.json()["id"])
    await procesar_documento(get_sessionmaker(), doc_id, ejecutor, VectorizadorFalso())
    _, frags = await _documento(doc_id)
    assert frags[0].metadata_jsonb["tipo_documento"] == "ADENDA"
    assert frags[0].metadata_jsonb["numero_adenda"] == 2
    assert frags[0].seccion == "ADENDA No. 2"
    assert "Tipo: ADENDA" in frags[0].contenido_vectorizado
