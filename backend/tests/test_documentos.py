"""Ingesta efímera. Con ASGITransport las BackgroundTasks terminan antes de que `client.post`
devuelva, así que tras la subida ya se puede consultar el estado final de la validación."""

import hashlib
import uuid

import pytest

from app.core.config import get_settings
from app.services.antivirus import get_scanner
from app.services.cola import get_cola
from tests.conftest import Org
from tests.fakes import ColaFalsa, ScannerFalso, archivos, subir
from tests.pdfs import MARCADOR_VIRUS, pdf


@pytest.fixture
async def expediente(org_a: Org) -> dict:
    return await org_a.crear_expediente(org_a.admin)


async def detalle(client, org: Org, expediente: dict, doc_id: str) -> dict:
    r = await client.get(
        f"/api/v1/expedientes/{expediente['id']}/documentos/{doc_id}", headers=org.admin
    )
    assert r.status_code == 200, r.text
    return r.json()


# ---------- Camino feliz ----------
async def test_subida_valida_queda_en_cola(client, org_a, expediente, scanner, cola, ephemeral_dir):
    contenido = pdf(paginas=3)
    r = await subir(client, org_a.admin, expediente["id"], contenido)
    assert r.status_code == 202, r.text
    doc = r.json()
    # La respuesta llega antes del antivirus.
    assert doc["estado_indexacion"] == "VALIDANDO"
    assert doc["sha256_original"] == hashlib.sha256(contenido).hexdigest()
    assert doc["tamano_bytes"] == len(contenido)
    assert doc["embedding_model"] == "text-embedding-3-small"

    final = await detalle(client, org_a, expediente, doc["id"])
    assert final["estado_indexacion"] == "EN_COLA"
    assert final["progreso"] == 15
    assert final["total_paginas"] == 3
    assert final["temp_file_purged"] is False
    assert final["actas_purga"] == []
    # El temporal se nombra por id (nunca con el nombre del cliente) y no queda .part.
    assert archivos(ephemeral_dir) == [f"{doc['id']}.pdf"]
    assert (ephemeral_dir / f"{doc['id']}.pdf").read_bytes() == contenido
    assert cola.encolados == [uuid.UUID(doc["id"])]
    assert scanner.escaneados == [f"{doc['id']}.pdf"]


async def test_nombre_con_ruta_se_reduce_al_nombre_base(client, org_a, expediente, scanner, cola):
    r = await subir(client, org_a.admin, expediente["id"], pdf(), nombre="..\\..\\etc\\x.pdf")
    assert r.status_code == 202
    assert r.json()["nombre_archivo_original"] == "x.pdf"


async def test_pdf_solo_con_clave_de_propietario_se_acepta(
    client, org_a, expediente, scanner, cola
):
    r = await subir(client, org_a.admin, expediente["id"], pdf(owner_password="propietario"))
    final = await detalle(client, org_a, expediente, r.json()["id"])
    assert final["estado_indexacion"] == "EN_COLA"


# ---------- Rechazos en segundo plano (quedan registrados y purgados) ----------
async def _assert_rechazado_y_purgado(client, org_a, expediente, r, ephemeral_dir, texto: str):
    assert r.status_code == 202, r.text
    doc = await detalle(client, org_a, expediente, r.json()["id"])
    assert doc["estado_indexacion"] == "ERROR_PURGADO"
    assert texto in doc["motivo_error"]
    assert doc["temp_file_purged"] is True
    assert archivos(ephemeral_dir) == []
    actas = doc["actas_purga"]
    assert len(actas) == 1
    assert actas[0]["motivo"] == "ERROR_VALIDACION"
    assert actas[0]["archivo_existia"] is True
    assert actas[0]["sha256_original"] == doc["sha256_original"]


async def test_pdf_con_contrasena(client, org_a, expediente, scanner, cola, ephemeral_dir):
    r = await subir(client, org_a.admin, expediente["id"], pdf(user_password="secreta"))
    await _assert_rechazado_y_purgado(client, org_a, expediente, r, ephemeral_dir, "contraseña")
    assert cola.encolados == []


async def test_pdf_corrupto(client, org_a, expediente, scanner, cola, ephemeral_dir):
    r = await subir(client, org_a.admin, expediente["id"], b"%PDF-1.7\n basura sin estructura")
    await _assert_rechazado_y_purgado(client, org_a, expediente, r, ephemeral_dir, "corrupto")


async def test_virus_detectado(client, org_a, expediente, scanner, cola, ephemeral_dir):
    r = await subir(client, org_a.admin, expediente["id"], pdf() + MARCADOR_VIRUS)
    await _assert_rechazado_y_purgado(client, org_a, expediente, r, ephemeral_dir, "Test.Marcador")
    assert cola.encolados == []


async def test_antivirus_caido_purga(client, app, org_a, expediente, cola, ephemeral_dir):
    app.dependency_overrides[get_scanner] = lambda: ScannerFalso(caido=True)
    r = await subir(client, org_a.admin, expediente["id"], pdf())
    await _assert_rechazado_y_purgado(client, org_a, expediente, r, ephemeral_dir, "antivirus")


# ---------- Rechazo inmediato: no es un PDF ----------
async def test_archivo_que_no_es_pdf(client, org_a, expediente, scanner, cola, ephemeral_dir):
    r = await subir(client, org_a.admin, expediente["id"], b"MZ\x90\x00 ejecutable disfrazado")
    assert r.status_code == 422
    cuerpo = r.json()
    assert "%PDF-" in cuerpo["detail"]
    assert cuerpo["documento"]["estado_indexacion"] == "ERROR_PURGADO"
    assert archivos(ephemeral_dir) == []
    assert scanner.escaneados == []  # se rechaza antes de llegar al antivirus
    doc = await detalle(client, org_a, expediente, cuerpo["documento"]["id"])
    assert [a["motivo"] for a in doc["actas_purga"]] == ["ERROR_VALIDACION"]


# ---------- Rechazos sin registro (antes de crear el documento) ----------
async def test_archivo_demasiado_grande(client, org_a, expediente, scanner, cola, ephemeral_dir):
    settings = get_settings()
    original = settings.max_upload_mb
    settings.max_upload_mb = 1
    try:
        r = await subir(client, org_a.admin, expediente["id"], pdf() + b"0" * (2 * 1024 * 1024))
    finally:
        settings.max_upload_mb = original
    assert r.status_code == 413
    assert archivos(ephemeral_dir) == []
    lista = await client.get(
        f"/api/v1/expedientes/{expediente['id']}/documentos", headers=org_a.admin
    )
    assert lista.json() == []


async def test_adenda_sin_numero(client, org_a, expediente, scanner, cola, ephemeral_dir):
    r = await subir(client, org_a.admin, expediente["id"], pdf(), tipo="ADENDA")
    assert r.status_code == 422
    assert archivos(ephemeral_dir) == []

    r = await subir(client, org_a.admin, expediente["id"], pdf(), tipo="ADENDA", numero_adenda=2)
    assert r.status_code == 202
    assert r.json()["numero_adenda"] == 2


async def test_tipo_documento_invalido(client, org_a, expediente, scanner, cola, ephemeral_dir):
    r = await subir(client, org_a.admin, expediente["id"], pdf(), tipo="FACTURA")
    assert r.status_code == 422
    assert archivos(ephemeral_dir) == []


async def test_sin_archivo(client, org_a, expediente, scanner, cola):
    r = await client.post(
        f"/api/v1/expedientes/{expediente['id']}/documentos",
        headers=org_a.admin,
        data={"tipo_documento": "PLIEGO"},
        files={"otro": ("x.txt", b"hola", "text/plain")},
    )
    assert r.status_code == 400


async def test_no_multipart(client, org_a, expediente, scanner, cola):
    r = await client.post(
        f"/api/v1/expedientes/{expediente['id']}/documentos",
        headers={**org_a.admin, "Content-Type": "application/pdf"},
        content=pdf(),
    )
    assert r.status_code == 415


async def test_duplicado_en_el_expediente(client, org_a, expediente, scanner, cola, ephemeral_dir):
    contenido = pdf()
    primero = await subir(client, org_a.admin, expediente["id"], contenido)
    r = await subir(client, org_a.admin, expediente["id"], contenido)
    assert r.status_code == 409
    assert r.json()["detail"]["documento_id"] == primero.json()["id"]
    assert archivos(ephemeral_dir) == [f"{primero.json()['id']}.pdf"]


async def test_tras_un_error_se_puede_volver_a_subir(client, org_a, expediente, app, cola):
    contenido = pdf()
    app.dependency_overrides[get_scanner] = lambda: ScannerFalso(caido=True)
    r1 = await subir(client, org_a.admin, expediente["id"], contenido)
    assert (await detalle(client, org_a, expediente, r1.json()["id"]))[
        "estado_indexacion"
    ] == "ERROR_PURGADO"

    app.dependency_overrides[get_scanner] = lambda: ScannerFalso()
    r2 = await subir(client, org_a.admin, expediente["id"], contenido)
    assert r2.status_code == 202
    assert (await detalle(client, org_a, expediente, r2.json()["id"]))[
        "estado_indexacion"
    ] == "EN_COLA"


# ---------- Autorización ----------
async def test_lector_no_puede_subir(client, org_a, expediente, scanner, cola, ephemeral_dir):
    uid, lector = await org_a.crear_usuario("lector@hospital-a.co", "LECTOR")
    await client.put(
        f"/api/v1/expedientes/{expediente['id']}/permisos/{uid}",
        headers=org_a.admin,
        json={"permiso": "LECTOR"},
    )
    r = await subir(client, lector, expediente["id"], pdf())
    assert r.status_code == 403
    assert archivos(ephemeral_dir) == []


async def test_otro_tenant_no_puede_subir_ni_ver(
    client, org_a, org_b, expediente, scanner, cola, ephemeral_dir
):
    r = await subir(client, org_b.admin, expediente["id"], pdf())
    assert r.status_code == 404
    assert archivos(ephemeral_dir) == []

    doc = (await subir(client, org_a.admin, expediente["id"], pdf())).json()
    base = f"/api/v1/expedientes/{expediente['id']}/documentos"
    assert (await client.get(base, headers=org_b.admin)).status_code == 404
    assert (await client.get(f"{base}/{doc['id']}", headers=org_b.admin)).status_code == 404
    assert (await client.delete(f"{base}/{doc['id']}", headers=org_b.admin)).status_code == 404


async def test_expediente_cerrado_no_acepta_documentos(client, org_a, expediente, scanner, cola):
    await client.patch(
        f"/api/v1/expedientes/{expediente['id']}", headers=org_a.admin, json={"estado": "CERRADO"}
    )
    r = await subir(client, org_a.admin, expediente["id"], pdf())
    assert r.status_code == 409


# ---------- Borrado garantizado ante errores internos ----------
async def test_error_interno_en_segundo_plano_purga_el_archivo(
    client, app, org_a, expediente, scanner, ephemeral_dir
):
    app.dependency_overrides[get_cola] = lambda: ColaFalsa(falla=True)
    r = await subir(client, org_a.admin, expediente["id"], pdf())
    assert r.status_code == 202
    assert archivos(ephemeral_dir) == []
    doc = await detalle(client, org_a, expediente, r.json()["id"])
    assert doc["estado_indexacion"] == "ERROR_PURGADO"
    assert "RuntimeError" in doc["motivo_error"]
    assert [a["motivo"] for a in doc["actas_purga"]] == ["ERROR_PROCESAMIENTO"]


# ---------- Listado y eliminación ----------
async def test_eliminar_documento_conserva_el_acta(
    client, org_a, expediente, scanner, cola, ephemeral_dir, postgres_url
):
    doc = (await subir(client, org_a.admin, expediente["id"], pdf())).json()
    base = f"/api/v1/expedientes/{expediente['id']}/documentos"
    assert len((await client.get(base, headers=org_a.admin)).json()) == 1

    assert (await client.delete(f"{base}/{doc['id']}", headers=org_a.admin)).status_code == 204
    assert archivos(ephemeral_dir) == []
    assert (await client.get(f"{base}/{doc['id']}", headers=org_a.admin)).status_code == 404

    import psycopg

    with psycopg.connect(postgres_url) as conn:
        fila = conn.execute(
            "SELECT motivo, documento_id, sha256_original, archivo_existia FROM actas_purga"
        ).fetchone()
    assert fila == ("DOCUMENTO_ELIMINADO", None, doc["sha256_original"], True)
