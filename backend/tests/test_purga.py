import os
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from app.core.db import get_sessionmaker
from app.core.enums import EstadoIndexacion as E
from app.models import ActaPurga, Documento, Fragmento
from app.services.estados import TransicionInvalida, puede_transicionar, transicionar
from app.services.purga import VerificacionFallida, barrer, finalizar_indexacion
from tests.fakes import archivos, subir
from tests.pdfs import pdf


# ---------- Máquina de estados ----------
def test_transiciones_validas_e_invalidas():
    assert puede_transicionar(E.EN_COLA, E.EXTRAYENDO_OCR)
    assert puede_transicionar(E.VECTORIZANDO, E.INDEXADO_Y_PURGADO)
    assert puede_transicionar(E.FRAGMENTANDO, E.ERROR_PURGADO)
    assert not puede_transicionar(E.EN_COLA, E.VECTORIZANDO)  # no se salta pasos
    assert not puede_transicionar(E.INDEXADO_Y_PURGADO, E.ERROR_PURGADO)  # final
    assert not puede_transicionar(E.ERROR_PURGADO, E.EN_COLA)

    doc = Documento(estado_indexacion=E.RECIBIDO)
    with pytest.raises(TransicionInvalida):
        transicionar(doc, E.INDEXADO_Y_PURGADO)


# ---------- Utilidades ----------
async def _documento_vectorizado(client, org_a, expediente, n_fragmentos: int, esperados: int):
    """Sube un PDF y simula lo que harán los Sprints 3-4: estados y fragmentos con embedding."""
    doc = (await subir(expediente["id"], pdf())).json()
    doc_id = uuid.UUID(doc["id"])
    async with get_sessionmaker()() as s:
        d = await s.get(Documento, doc_id)
        for estado in (E.EXTRAYENDO_OCR, E.FRAGMENTANDO, E.VECTORIZANDO):
            transicionar(d, estado)
        d.total_chunks_esperados = esperados
        for orden in range(1, n_fragmentos + 1):
            s.add(
                Fragmento(
                    tenant_id=d.tenant_id,
                    expediente_id=d.expediente_id,
                    documento_id=d.id,
                    orden=orden,
                    pagina_inicio=1,
                    pagina_fin=1,
                    seccion="CAPÍTULO 1",
                    contenido_texto=f"Fragmento {orden}",
                    contenido_vectorizado=f"[Expediente: X] Fragmento {orden}",
                    token_count=10,
                    embedding_model="text-embedding-3-small",
                    embedding=[0.1] * 1536,
                )
            )
        await s.commit()
    return doc_id


async def _finalizar(doc_id):
    async with get_sessionmaker()() as s:
        d = await s.get(Documento, doc_id)
        await finalizar_indexacion(s, d)


async def _estado(doc_id) -> tuple[Documento, list[ActaPurga], int]:
    async with get_sessionmaker()() as s:
        d = await s.get(Documento, doc_id)
        actas = list(await s.scalars(select(ActaPurga).where(ActaPurga.documento_id == doc_id)))
        n = await s.scalar(
            select(func.count()).select_from(Fragmento).where(Fragmento.documento_id == doc_id)
        )
        return d, actas, n


@pytest.fixture
async def expediente(org_a, cola):
    return await org_a.crear_expediente(org_a.admin)


# ---------- Verificación previa al borrado (Paso 9) ----------
async def test_indexacion_completa_purga_inmediata(client, org_a, expediente, ephemeral_dir):
    doc_id = await _documento_vectorizado(client, org_a, expediente, n_fragmentos=2, esperados=2)
    assert archivos(ephemeral_dir) == [f"{doc_id}.pdf"]

    await _finalizar(doc_id)

    d, actas, n = await _estado(doc_id)
    assert d.estado_indexacion == E.INDEXADO_Y_PURGADO
    assert d.temp_file_purged is True and d.purged_at is not None
    assert d.total_chunks_guardados == 2
    assert n == 2  # los fragmentos se conservan: el sistema sigue consultable
    assert archivos(ephemeral_dir) == []
    assert [
        (a.motivo, a.chunks_esperados, a.chunks_verificados, a.archivo_existia) for a in actas
    ] == [("INDEXADO", 2, 2, True)]


async def test_indexacion_incompleta_no_se_da_por_buena(client, org_a, expediente, ephemeral_dir):
    doc_id = await _documento_vectorizado(client, org_a, expediente, n_fragmentos=2, esperados=3)
    with pytest.raises(VerificacionFallida):
        await _finalizar(doc_id)

    d, actas, n = await _estado(doc_id)
    assert d.estado_indexacion == E.ERROR_PURGADO
    assert "Se esperaban 3 fragmentos y hay 2" in d.motivo_error
    assert n == 0  # un índice parcial no debe quedar consultable
    assert archivos(ephemeral_dir) == []
    assert actas[0].motivo == "ERROR_PROCESAMIENTO"


async def test_cero_fragmentos_esperados_es_error(client, org_a, expediente, ephemeral_dir):
    doc_id = await _documento_vectorizado(client, org_a, expediente, n_fragmentos=0, esperados=0)
    with pytest.raises(VerificacionFallida, match="mayor que 0"):
        await _finalizar(doc_id)
    d, _, _ = await _estado(doc_id)
    assert d.estado_indexacion == E.ERROR_PURGADO


# ---------- Política DIFERIDO_1H ----------
async def test_purga_diferida(client, org_a, expediente, ephemeral_dir):
    org_a.politica_de_borrado("DIFERIDO_1H")
    doc_id = await _documento_vectorizado(client, org_a, expediente, n_fragmentos=1, esperados=1)
    await _finalizar(doc_id)

    d, actas, _ = await _estado(doc_id)
    assert d.estado_indexacion == E.INDEXADO_PENDIENTE_PURGA
    assert d.purga_programada_at is not None and actas == []
    assert archivos(ephemeral_dir) == [f"{doc_id}.pdf"]

    # Antes del plazo, el barrido no la toca.
    resumen = await barrer(get_sessionmaker())
    assert resumen.diferidas == 0
    assert archivos(ephemeral_dir) == [f"{doc_id}.pdf"]

    resumen = await barrer(get_sessionmaker(), ahora=datetime.now(UTC) + timedelta(minutes=61))
    assert resumen.diferidas == 1
    d, actas, _ = await _estado(doc_id)
    assert d.estado_indexacion == E.INDEXADO_Y_PURGADO
    assert archivos(ephemeral_dir) == []
    assert actas[0].motivo == "INDEXADO"


# ---------- Barrido de documentos atascados y huérfanos ----------
async def test_documento_atascado_se_purga_por_timeout(client, org_a, expediente, ephemeral_dir):
    doc = (await subir(expediente["id"], pdf())).json()
    doc_id = uuid.UUID(doc["id"])

    assert (await barrer(get_sessionmaker())).timeouts == 0
    async with get_sessionmaker()() as s:
        await s.execute(
            update(Documento)
            .where(Documento.id == doc_id)
            .values(estado_actualizado_at=datetime.now(UTC) - timedelta(hours=7))
        )
        await s.commit()

    assert (await barrer(get_sessionmaker())).timeouts == 1
    d, actas, _ = await _estado(doc_id)
    assert d.estado_indexacion == E.ERROR_PURGADO
    assert "EN_COLA" in d.motivo_error
    assert actas[0].motivo == "TIMEOUT"
    assert archivos(ephemeral_dir) == []


def _envejecer(ruta, minutos: int) -> None:
    t = time.time() - minutos * 60
    os.utime(ruta, (t, t))


async def test_archivos_huerfanos(client, org_a, expediente, ephemeral_dir):
    activo = (await subir(expediente["id"], pdf())).json()
    ruta_activo = ephemeral_dir / f"{activo['id']}.pdf"
    huerfano_viejo = ephemeral_dir / f"{uuid.uuid4()}.part"
    huerfano_nuevo = ephemeral_dir / f"{uuid.uuid4()}.part"  # subida en curso
    basura = ephemeral_dir / "algo-raro.tmp"
    for ruta in (huerfano_viejo, huerfano_nuevo, basura):
        ruta.write_bytes(b"x")
    for ruta in (ruta_activo, huerfano_viejo, basura):
        _envejecer(ruta, 30)

    resumen = await barrer(get_sessionmaker())

    assert resumen.huerfanos == 2
    assert sorted(archivos(ephemeral_dir)) == sorted([ruta_activo.name, huerfano_nuevo.name])
    async with get_sessionmaker()() as s:
        motivos = list(await s.scalars(select(ActaPurga.motivo)))
    assert motivos == ["HUERFANO", "HUERFANO"]


async def test_archivo_de_documento_ya_finalizado_es_huerfano(
    client, org_a, expediente, ephemeral_dir
):
    doc_id = await _documento_vectorizado(client, org_a, expediente, n_fragmentos=1, esperados=1)
    await _finalizar(doc_id)
    residuo = ephemeral_dir / f"{doc_id}.pdf"
    residuo.write_bytes(b"residuo")  # p. ej. una restauración de backup del disco
    _envejecer(residuo, 30)

    assert (await barrer(get_sessionmaker())).huerfanos == 1
    assert archivos(ephemeral_dir) == []
