"""Cifrado en la base de lo que la persona pregunta y se le responde (sprint 42)."""

import base64
import json
import os

import psycopg
import pytest
from sqlalchemy import select

from app import cli
from app.core.config import Settings
from app.core.db import fijar_sistema, get_sessionmaker
from app.models import Consulta
from app.privacidad.cifrado_columnas import CifradorDatos, ErrorCifrado

CLAVE = os.environ["DATOS_CLAVE"]
OTRA = base64.b64encode(b"o" * 32).decode()


def test_cifrar_y_descifrar_con_un_vector_distinto_cada_vez():
    c = CifradorDatos(CLAVE)
    texto = "Hemoglobina 13,2 g/dL — ¿está bien?"
    uno, dos = c.cifrar(texto), c.cifrar(texto)
    assert uno.startswith("mtd1:") and uno != dos and "Hemoglobina" not in uno
    assert c.descifrar(uno) == c.descifrar(dos) == texto


def test_un_dato_alterado_o_con_otra_clave_no_se_lee():
    cifrado = CifradorDatos(CLAVE).cifrar("dato")
    alterado = cifrado[:-4] + ("A" if cifrado[-4] != "A" else "B") + cifrado[-3:]
    with pytest.raises(ErrorCifrado):
        CifradorDatos(CLAVE).descifrar(alterado)
    with pytest.raises(ErrorCifrado):
        CifradorDatos(OTRA).descifrar(cifrado)


@pytest.mark.parametrize("mala", ["no-es-base64!!", base64.b64encode(b"corta").decode()])
def test_la_clave_debe_ser_de_32_bytes(mala):
    with pytest.raises(ErrorCifrado, match="32 bytes"):
        CifradorDatos(mala)


def test_produccion_exige_la_clave():
    fatales, _ = Settings(_env_file=None, datos_clave="").problemas_produccion()
    assert any("DATOS_CLAVE" in f for f in fatales)
    fatales, _ = Settings(_env_file=None, datos_clave="corta").problemas_produccion()
    assert any("DATOS_CLAVE" in f for f in fatales)
    fatales, _ = Settings(_env_file=None, datos_clave=CLAVE).problemas_produccion()
    assert not any("DATOS_CLAVE" in f for f in fatales)


# ---------- en la base ----------
def _filas(postgres_url: str) -> list[tuple]:
    with psycopg.connect(os.environ["TEST_DATABASE_ADMIN_URL"]) as conn:
        return conn.execute("select pregunta, respuesta::text from consultas").fetchall()


def _cuerpo(org, expediente, pregunta):
    return {
        "tenant_id": str(org.tenant_id),
        "expediente_id": expediente["id"],
        "usuario_id": str(org.admin_id),
        "pregunta": pregunta,
    }


async def _historial(client, org, expediente):
    r = await client.get(
        "/internal/v1/consultas",
        headers=org.admin,
        params={
            "tenant_id": str(org.tenant_id),
            "expediente_id": expediente["id"],
            "usuario_id": str(org.admin_id),
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


async def test_en_la_base_queda_cifrado_y_la_persona_lo_ve_normal(client, org_a, postgres_url):
    expediente = await org_a.crear_expediente()
    pregunta = "¿Cuántos miligramos de losartán debo tomar?"  # respuesta fija, sin modelo
    r = await client.post(
        "/internal/v1/consultas", headers=org_a.admin, json=_cuerpo(org_a, expediente, pregunta)
    )
    assert r.status_code == 200, r.text

    [(guardada, respuesta)] = _filas(postgres_url)
    assert guardada.startswith("mtd1:") and "losart" not in guardada
    assert set(json.loads(respuesta)) == {"cifrado"} and "miligramos" not in respuesta

    [h] = await _historial(client, org_a, expediente)
    assert h["pregunta"] == pregunta and h["consultaId"] == r.json()["consultaId"]


async def test_lo_guardado_antes_se_sigue_leyendo_y_se_puede_cifrar(client, org_a, postgres_url):
    expediente = await org_a.crear_expediente()
    with psycopg.connect(os.environ["TEST_DATABASE_ADMIN_URL"], autocommit=True) as conn:
        conn.execute(
            "insert into consultas (tenant_id, expediente_id, usuario_id, pregunta, respuesta, "
            "sin_evidencia, modelo_embeddings, latencia_ms) values (%s, %s, %s, %s, %s, false, 'm', 1)",
            (
                org_a.tenant_id,
                expediente["id"],
                org_a.admin_id,
                "pregunta antigua",
                '{"huella": "h1", "x": 1}',
            ),
        )
    [h] = await _historial(client, org_a, expediente)
    assert h["pregunta"] == "pregunta antigua" and h["x"] == 1

    assert await cli._cifrar_historial() == 1
    [(guardada, respuesta)] = _filas(postgres_url)
    assert guardada.startswith("mtd1:")
    # la huella de la línea de tiempo no es un dato de salud y se necesita para encontrarla
    assert set(json.loads(respuesta)) == {"cifrado", "huella"}
    assert await cli._cifrar_historial() == 0  # repetirlo no vuelve a cifrar
    [h] = await _historial(client, org_a, expediente)
    assert h["pregunta"] == "pregunta antigua" and h["x"] == 1


async def test_sin_la_clave_no_se_muestra_el_texto_cifrado(client, org_a, monkeypatch):
    expediente = await org_a.crear_expediente()
    await client.post(
        "/internal/v1/consultas",
        headers=org_a.admin,
        json=_cuerpo(org_a, expediente, "¿Qué dosis tomo?"),
    )
    monkeypatch.setattr("app.privacidad.cifrado_columnas.clave_configurada", lambda: "")
    with pytest.raises(ErrorCifrado, match="DATOS_CLAVE"):
        async with get_sessionmaker()() as s:
            fijar_sistema(s)
            await s.scalar(select(Consulta))


async def test_cifrar_historial_tambien_cifra_lo_extraido_para_la_linea(
    client, org_a, monkeypatch
):
    expediente = await org_a.crear_expediente()
    with psycopg.connect(os.environ["TEST_DATABASE_ADMIN_URL"]) as conn:
        [doc] = conn.execute(
            "insert into documentos (tenant_id, expediente_id, nombre_archivo_original, tipo_documento, "
            "sha256_original, tamano_bytes, estado_indexacion, embedding_model) values "
            "(%s, %s, 'a.pdf', 'PLIEGO', %s, 1, 'INDEXADO_Y_PURGADO', 'gemini-embedding-001') returning id",
            (org_a.tenant_id, expediente["id"], "0" * 64),
        ).fetchone()
        conn.execute(
            "insert into extracciones_linea (documento_id, tenant_id, expediente_id, version, "
            "huella_fragmentos, datos) values (%s, %s, %s, 'v', 'h', %s)",
            (doc, org_a.tenant_id, expediente["id"], json.dumps({"valores": [{"analito": "Glucosa"}]})),
        )

    assert await cli._cifrar_historial() == 1
    with psycopg.connect(os.environ["TEST_DATABASE_ADMIN_URL"]) as conn:
        [(crudo,)] = conn.execute("select datos::text from extracciones_linea").fetchall()
    assert "mtd1:" in crudo and "Glucosa" not in crudo
    assert await cli._cifrar_historial() == 0
