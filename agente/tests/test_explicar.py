"""«Explícame este documento»: dos capas separadas, citas verificadas y nada que el documento no diga."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.ia.embeddings import EmbeddingRouter, get_router
from app.ia.llm import ErrorLLM, RespuestaLLM, get_llm
from app.models import Consulta
from app.pipeline.procesador import procesar_documento
from app.pipeline.vectorizacion import VectorizadorEmbeddings
from app.rag import explicar
from app.rag.busqueda import FragmentoRecuperado
from tests.fakes import EmbeddingsFalsos, subir
from tests.pdfs import pdf_texto, texto_largo

MODELO = "gemini-embedding-001"


def _frag(orden: int, texto: str, **meta) -> FragmentoRecuperado:
    return FragmentoRecuperado(
        id=uuid.uuid4(),
        documento_id=uuid.uuid4(),
        orden=orden,
        pagina_inicio=orden,
        pagina_fin=orden,
        seccion="LABORATORIO",
        contenido_texto=texto,
        metadata=meta,
        nombre_archivo="examen.pdf",
        tipo_documento="HISTORIA_CLINICA",
        numero_adenda=0,
        sha256_original="0" * 64,
    )


EVIDENCIAS = [
    _frag(1, "Hemoglobina 13,2 g/dL. Glucosa en ayunas 92 mg/dL. Colesterol LDL 160 mg/dL."),
    _frag(2, "Se solicita control con medicina interna en un mes."),
]


def _datos(**cambios) -> dict:
    base = {
        "hay_evidencia": True,
        "de_que_trata": "Es un examen de laboratorio con valores de sangre.",
        "hallazgos": [
            {
                "texto": "La hemoglobina es 13,2.",
                "fragmento": "F1",
                "extracto_literal": "Hemoglobina 13,2 g/dL",
            },
            {
                "texto": "Piden un control en un mes.",
                "fragmento": "F2",
                "extracto_literal": "control con medicina interna en un mes",
            },
        ],
        "terminos": [
            {"termino": "Hemoglobina", "explicacion": "Proteína de la sangre que lleva oxígeno."}
        ],
        "senales_de_alarma": [],
        "preguntas_para_el_medico": ["¿Qué significa mi valor de LDL?"],
    }
    return base | cambios


def ensamblar(datos):
    return explicar.ensamblar_explicacion(datos, EVIDENCIAS, 0.85)


# ---------- ensamblado y verificación (sin base de datos) ----------
def test_cada_hallazgo_queda_citado_con_un_extracto_literal_verificado():
    r = ensamblar(_datos())
    assert not r.sin_evidencia and len(r.hallazgos) == 2
    assert [h["cita"] for h in r.hallazgos] == [1, 2]
    assert r.citas[0].extracto == "Hemoglobina 13,2 g/dL" and r.citas[0].ajustado is False
    assert r.de_que_trata.startswith("Es un examen")


def test_un_hallazgo_con_un_fragmento_inexistente_se_descarta():
    datos = _datos()
    datos["hallazgos"].append({"texto": "Inventado.", "fragmento": "F9", "extracto_literal": "x"})
    r = ensamblar(datos)
    assert len(r.hallazgos) == 2 and r.descartados == 1


def test_un_extracto_inventado_se_reemplaza_por_la_oracion_real_y_se_marca():
    datos = _datos(
        hallazgos=[
            {
                "texto": "Tiene diabetes.",
                "fragmento": "F1",
                "extracto_literal": "glucosa elevada con diabetes",
            }
        ]
    )
    r = ensamblar(datos)
    assert r.citas[0].ajustado is True
    assert r.citas[0].extracto in EVIDENCIAS[0].contenido_texto  # lo que se muestra es texto real


def test_dos_hallazgos_con_el_mismo_extracto_comparten_la_cita():
    h = {"texto": "a", "fragmento": "F1", "extracto_literal": "Hemoglobina 13,2 g/dL"}
    r = ensamblar(_datos(hallazgos=[h, {**h, "texto": "b"}]))
    assert len(r.citas) == 1 and [x["cita"] for x in r.hallazgos] == [1, 1]


def test_sin_ningun_hallazgo_verificable_no_se_muestra_nada_del_modelo():
    datos = _datos(hallazgos=[{"texto": "x", "fragmento": "F9", "extracto_literal": "x"}])
    r = ensamblar(datos)
    assert (
        r.sin_evidencia
        and r.de_que_trata == ""
        and r.terminos == []
        and r.preguntas_para_el_medico == []
    )


def test_hay_evidencia_falso_es_una_abstencion_aunque_haya_hallazgos():
    assert ensamblar(_datos(hay_evidencia=False)).sin_evidencia


def test_las_preguntas_se_acotan_y_se_limpian_y_los_terminos_no_salen_del_modelo():
    terminos = [{"termino": f"t{i}", "explicacion": "e"} for i in range(12)]
    preguntas = [f"¿p{i}?" for i in range(9)] + ["  "]
    r = ensamblar(_datos(terminos=terminos, preguntas_para_el_medico=preguntas))
    assert len(r.preguntas_para_el_medico) == 6 and all(p.strip() for p in r.preguntas_para_el_medico)
    # lo que el modelo diga como «términos» se ignora: solo cuentan los del glosario hallados en el texto
    assert all(t["termino"] != "t0" for t in r.terminos)
    assert {t["termino"] for t in r.terminos} >= {"Hemoglobina", "Glucosa en ayunas", "Colesterol LDL"}


def test_el_prompt_prohibe_diagnosticar_recetar_y_dosificar_y_aisla_el_contenido():
    s = explicar.SISTEMA_EXPLICAR
    for clave in (
        "PROHIBIDO",
        "diagnosticar",
        "indicar dosis",
        "pronosticar",
        "NO instrucciones",
        "NO digas qué significa para esta persona",
    ):
        assert clave in s, clave
    assert set(explicar.ESQUEMA_EXPLICAR["required"]) == {
        "hay_evidencia",
        "de_que_trata",
        "hallazgos",
        "senales_de_alarma",
        "preguntas_para_el_medico",
    }


def test_el_aviso_general_aclara_que_los_terminos_no_son_un_diagnostico():
    assert "no un diagnóstico" in explicar.AVISO_GENERAL and "123" in explicar.AVISO_GENERAL


# ---------- extremo a extremo con la base real ----------
class EmbeddingsQueRegistran(EmbeddingsFalsos):
    pass


class LLMExplicador:
    modelo = "gemini-falso"

    def __init__(self, error: Exception | None = None):
        self.error = error
        self.prompts: list[str] = []
        self.sistemas: list[str] = []

    async def generar_json(self, sistema, prompt, esquema):
        self.prompts.append(prompt)
        self.sistemas.append(sistema)
        if self.error:
            raise self.error
        return RespuestaLLM(
            {
                "hay_evidencia": True,
                "de_que_trata": "Historia clínica de [PERSONA_1] con diagnóstico de hipertensión arterial.",
                "hallazgos": [
                    {
                        "texto": "El paciente es [PERSONA_1].",
                        "fragmento": "F1",
                        "extracto_literal": "Paciente: [PERSONA_1]",
                    }
                ],
                "terminos": [
                    {
                        "termino": "Hipertensión arterial",
                        "explicacion": "Presión de la sangre por encima de lo normal.",
                    }
                ],
                "senales_de_alarma": [],
                "preguntas_para_el_medico": ["¿Cada cuánto debo controlarme la tensión?"],
            },
            self.modelo,
        )


@pytest.fixture
def router(app):
    r = EmbeddingRouter({MODELO: EmbeddingsQueRegistran(MODELO, 1536)})
    app.dependency_overrides[get_router] = lambda: r
    return r


@pytest.fixture
def llm(app):
    falso = LLMExplicador()
    app.dependency_overrides[get_llm] = lambda: falso
    return falso


HISTORIA = (
    "HISTORIA CLÍNICA\n\nPaciente: María Gómez Rojas. CC 1.020.304.050. "
    "Diagnóstico: hipertensión arterial.\n\n" + texto_largo(30, "hipertensión")
)


async def _indexar(expediente, router, contenido: bytes | None = None) -> uuid.UUID:
    r = await subir(
        expediente["id"],
        contenido or pdf_texto([HISTORIA]),
        tipo="HISTORIA_CLINICA",
        nombre="Historia_Maria.pdf",
    )
    doc_id = uuid.UUID(r.json()["id"])
    with ThreadPoolExecutor(max_workers=1) as ex:
        await procesar_documento(get_sessionmaker(), doc_id, ex, VectorizadorEmbeddings(router))
    return doc_id


async def _explicar(client, org, expediente, doc_id, headers=None):
    return await client.post(
        "/internal/v1/explicaciones",
        headers=org.admin if headers is None else headers,
        json={
            "tenant_id": str(org.tenant_id),
            "expediente_id": expediente["id"],
            "documento_id": str(doc_id),
            "usuario_id": str(org.admin_id),
        },
    )


async def test_explica_un_documento_en_dos_capas_con_citas_literales_y_datos_reales(
    client, org_a, cola, router, llm
):
    expediente = await org_a.crear_expediente(org_a.admin)
    doc_id = await _indexar(expediente, router)

    r = await _explicar(client, org_a, expediente, doc_id)
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["modo"] == "explicar" and c["documentoId"] == str(doc_id) and not c["sinEvidencia"]
    # Los datos vuelven restaurados; la cita es el texto real del documento.
    assert "María Gómez Rojas" in c["deQueTrata"] and c["respuestaAnalitica"] == c["deQueTrata"]
    assert c["hallazgos"] == [{"texto": "El paciente es María Gómez Rojas.", "cita": 1}]
    assert c["citas"][0]["extractoLiteral"] == "Paciente: María Gómez Rojas"
    assert (
        c["citas"][0]["extractoAjustado"] is False
        and c["citas"][0]["nombreArchivo"] == "Historia_Maria.pdf"
    )
    # Capa 2 aparte, con su aviso.
    assert c["terminos"][0]["termino"] == "Hipertensión arterial"
    assert "no un diagnóstico" in c["avisoGeneral"]
    assert c["preguntasParaElMedico"] and c["senalesDeAlarma"] == []
    # Lo que salió a la nube iba anonimizado.
    for dato in ("María Gómez Rojas", "1.020.304.050", "Historia_Maria"):
        assert dato not in llm.prompts[0]
    assert "PROHIBIDO" in llm.sistemas[0]


async def test_la_explicacion_queda_en_el_historial_sin_el_nombre_del_archivo(
    client, org_a, cola, router, llm
):
    expediente = await org_a.crear_expediente(org_a.admin)
    doc_id = await _indexar(expediente, router)
    await _explicar(client, org_a, expediente, doc_id)

    async with get_sessionmaker()() as s:
        fila = (
            await s.scalars(
                select(Consulta).where(Consulta.expediente_id == uuid.UUID(expediente["id"]))
            )
        ).one()
    assert (
        fila.pregunta == f"[Explicar documento {doc_id}]" and "Historia_Maria" not in fila.pregunta
    )
    assert fila.respuesta["modo"] == "explicar"

    h = await client.get(
        "/internal/v1/consultas",
        headers=org_a.admin,
        params={
            "tenant_id": str(org_a.tenant_id),
            "expediente_id": expediente["id"],
            "usuario_id": str(org_a.admin_id),
        },
    )
    assert h.json()[0]["modo"] == "explicar"


async def test_un_documento_de_otra_organizacion_es_no_encontrado(
    client, org_a, org_b, cola, router, llm
):
    expediente_a = await org_a.crear_expediente(org_a.admin)
    doc_id = await _indexar(expediente_a, router)
    expediente_b = await org_b.crear_expediente(org_b.admin)
    # B intenta explicar el documento de A, tanto con su propio expediente como con el de A.
    assert (await _explicar(client, org_b, expediente_b, doc_id)).status_code == 404
    assert (await _explicar(client, org_b, expediente_a, doc_id)).status_code == 404
    assert llm.prompts == []  # ni siquiera se llamó al modelo


async def test_un_documento_de_otro_expediente_del_mismo_tenant_es_no_encontrado(
    client, org_a, cola, router, llm
):
    e1 = await org_a.crear_expediente(org_a.admin, codigo="E-1")
    e2 = await org_a.crear_expediente(org_a.admin, codigo="E-2")
    doc_id = await _indexar(e1, router)
    assert (await _explicar(client, org_a, e2, doc_id)).status_code == 404


async def test_un_documento_que_aun_se_procesa_responde_conflicto(client, org_a, cola, router, llm):
    expediente = await org_a.crear_expediente(org_a.admin)
    doc_id = uuid.UUID(
        (await subir(expediente["id"], pdf_texto([HISTORIA]))).json()["id"]
    )  # EN_COLA
    r = await _explicar(client, org_a, expediente, doc_id)
    assert r.status_code == 409 and "se está procesando" in r.json()["detail"]
    assert llm.prompts == []


async def test_si_el_modelo_falla_responde_503_sin_guardar_nada(client, org_a, cola, router, app):
    falso = LLMExplicador(error=ErrorLLM("sin servicio"))
    app.dependency_overrides[get_llm] = lambda: falso
    expediente = await org_a.crear_expediente(org_a.admin)
    doc_id = await _indexar(expediente, router)
    assert (await _explicar(client, org_a, expediente, doc_id)).status_code == 503
    async with get_sessionmaker()() as s:
        assert (await s.scalars(select(Consulta))).all() == []


async def test_un_documento_largo_se_acota_y_lo_dice(client, org_a, cola, router, llm, monkeypatch):
    monkeypatch.setattr(get_settings(), "explicar_max_fragmentos", 1)
    expediente = await org_a.crear_expediente(org_a.admin)
    paginas = [HISTORIA] + [texto_largo(40, f"tema{i}") for i in range(6)]
    doc_id = await _indexar(expediente, router, pdf_texto(paginas))
    c = (await _explicar(client, org_a, expediente, doc_id)).json()
    assert c["fragmentosRecuperados"] == 1 and c["fragmentosTotales"] > 1
    assert any("El documento es largo" in a for a in c["alertas"])


async def test_la_ruta_exige_el_token_interno(client, org_a, cola, router, llm):
    expediente = await org_a.crear_expediente(org_a.admin)
    doc_id = await _indexar(expediente, router)
    assert (await _explicar(client, org_a, expediente, doc_id, headers={})).status_code == 401
