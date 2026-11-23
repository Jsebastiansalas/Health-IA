"""Lo que sale a la nube va anonimizado; lo que ve el usuario y lo que se cita, no.

Extremo a extremo con la base real: se indexa una historia clínica con datos personales y se comprueba
(1) qué recibe el proveedor de embeddings al indexar y al preguntar, (2) qué recibe el LLM, y
(3) que la respuesta y la cita vuelven con los datos reales y el extracto sigue siendo literal.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.ia.embeddings import EmbeddingRouter, get_router
from app.ia.llm import RespuestaLLM, get_llm
from app.models import Fragmento
from app.pipeline.procesador import procesar_documento
from app.pipeline.vectorizacion import VectorizadorEmbeddings
from tests.fakes import EmbeddingsFalsos, subir
from tests.pdfs import pdf_texto, texto_largo

MODELO = "gemini-embedding-001"
DATOS = ["María Gómez Rojas", "1.020.304.050", "300 123 4567", "Historia_Maria_Gomez"]


class EmbeddingsQueRegistran(EmbeddingsFalsos):
    """Guarda cada texto que recibe: es exactamente lo que vería el proveedor."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.textos: list[str] = []

    async def embeber(self, textos, tarea):
        self.textos += textos
        return await super().embeber(textos, tarea)


class LLMQueRegistra:
    modelo = "gemini-falso"

    def __init__(self):
        self.prompts: list[str] = []

    async def generar_json(self, sistema, prompt, esquema):
        self.prompts.append(prompt)
        # El modelo ve marcadores y los usa, también dentro del extracto «literal».
        return RespuestaLLM(
            {
                "respuesta": "El paciente [PERSONA_1] tiene hipertensión arterial.",
                "hay_evidencia": True,
                "citas": [{"fragmento": "F1", "extracto_literal": "Paciente: [PERSONA_1]"}],
                "alertas": [],
            },
            self.modelo,
        )


@pytest.fixture
def embeddings(app):
    e = EmbeddingsQueRegistran(MODELO, 1536)
    r = EmbeddingRouter({MODELO: e})
    app.dependency_overrides[get_router] = lambda: r
    return e, r


@pytest.fixture
def llm(app):
    falso = LLMQueRegistra()
    app.dependency_overrides[get_llm] = lambda: falso
    return falso


HISTORIA = (
    "HISTORIA CLÍNICA\n\nPaciente: María Gómez Rojas. CC 1.020.304.050. Teléfono: 300 123 4567. "
    "Diagnóstico: hipertensión arterial.\n\n" + texto_largo(30, "hipertensión")
)
PREGUNTA = "¿Qué diagnóstico tiene el paciente: María Gómez Rojas, CC 1.020.304.050?"


async def _indexar(expediente, router):
    contenido = pdf_texto([HISTORIA])
    r = await subir(
        expediente["id"], contenido, tipo="HISTORIA_CLINICA", nombre="Historia_Maria_Gomez.pdf"
    )
    doc_id = uuid.UUID(r.json()["id"])
    with ThreadPoolExecutor(max_workers=1) as ex:
        await procesar_documento(get_sessionmaker(), doc_id, ex, VectorizadorEmbeddings(router))
    return doc_id


async def _preguntar(client, org, expediente):
    return await client.post(
        "/internal/v1/consultas",
        headers=org.admin,
        json={
            "tenant_id": str(org.tenant_id),
            "expediente_id": expediente["id"],
            "usuario_id": str(org.admin_id),
            "pregunta": PREGUNTA,
        },
    )


async def test_al_indexar_el_proveedor_de_embeddings_no_ve_datos_personales(
    client, org_a, cola, embeddings
):
    espia, router = embeddings
    expediente = await org_a.crear_expediente(org_a.admin)
    doc_id = await _indexar(expediente, router)

    enviado = "\n".join(espia.textos)
    assert enviado, "se esperaba que se vectorizaran fragmentos"
    for dato in DATOS:
        assert dato not in enviado, f"al proveedor llegó: {dato}"

    async with get_sessionmaker()() as s:
        filas = (await s.scalars(select(Fragmento).where(Fragmento.documento_id == doc_id))).all()
    # Lo guardado y lo que se muestra es el original; lo que se vectoriza, enmascarado.
    assert any("María Gómez Rojas" in f.contenido_texto for f in filas)
    assert all("María Gómez Rojas" not in f.contenido_vectorizado for f in filas)
    assert all("Historia_Maria_Gomez" not in f.contenido_vectorizado for f in filas)
    assert any("hipertensión" in f.contenido_vectorizado for f in filas)  # lo clínico se conserva


async def test_al_preguntar_el_llm_y_los_embeddings_solo_ven_marcadores(
    client, org_a, cola, embeddings, llm
):
    espia, router = embeddings
    expediente = await org_a.crear_expediente(org_a.admin)
    await _indexar(expediente, router)
    antes = len(espia.textos)

    r = await _preguntar(client, org_a, expediente)
    assert r.status_code == 200, r.text

    consulta_nube = "\n".join(espia.textos[antes:])
    prompt = llm.prompts[0]
    for dato in DATOS:
        assert dato not in consulta_nube, f"a embeddings llegó: {dato}"
        assert dato not in prompt, f"al LLM llegó: {dato}"
    assert "[PERSONA_1]" in prompt and "hipertensión" in prompt
    assert 'documento="documento-1"' in prompt  # el nombre del archivo no sale


async def test_la_respuesta_y_la_cita_vuelven_con_los_datos_reales_y_el_extracto_sigue_literal(
    client, org_a, cola, embeddings, llm
):
    _, router = embeddings
    expediente = await org_a.crear_expediente(org_a.admin)
    await _indexar(expediente, router)

    cuerpo = (await _preguntar(client, org_a, expediente)).json()
    assert (
        cuerpo["respuestaAnalitica"] == "El paciente María Gómez Rojas tiene hipertensión arterial."
    )
    cita = cuerpo["citas"][0]
    assert cita["extractoLiteral"] == "Paciente: María Gómez Rojas"
    assert cita["extractoAjustado"] is False  # se verificó contra el texto original
    assert cita["nombreArchivo"] == "Historia_Maria_Gomez.pdf"  # la UI muestra el nombre real
    assert not cuerpo["sinEvidencia"]


async def test_con_el_interruptor_apagado_no_se_enmascara(
    client, org_a, cola, embeddings, llm, monkeypatch
):
    monkeypatch.setattr(get_settings(), "anonimizar_antes_de_nube", False)
    espia, router = embeddings
    expediente = await org_a.crear_expediente(org_a.admin)
    await _indexar(expediente, router)
    await _preguntar(client, org_a, expediente)
    assert "María Gómez Rojas" in "\n".join(espia.textos)
    assert "María Gómez Rojas" in llm.prompts[0]


async def test_con_el_interruptor_apagado_la_cabecera_conserva_el_nombre_del_archivo(
    client, org_a, cola, embeddings, monkeypatch
):
    monkeypatch.setattr(get_settings(), "anonimizar_antes_de_nube", False)
    _, router = embeddings
    expediente = await org_a.crear_expediente(org_a.admin)
    doc_id = await _indexar(expediente, router)
    async with get_sessionmaker()() as s:
        fila = (await s.scalars(select(Fragmento).where(Fragmento.documento_id == doc_id))).first()
    assert "Doc: Historia_Maria_Gomez.pdf" in fila.contenido_vectorizado
