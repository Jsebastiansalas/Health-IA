"""Cruce medicamentos de los documentos ↔ fichas técnicas: dos citas por advertencia, sin elegir ni dosificar."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.ia.embeddings import EmbeddingRouter, get_router
from app.ia.llm import ErrorLLM, RespuestaLLM, get_llm
from app.medicamentos import fichas
from app.models import Consulta
from app.pipeline.procesador import procesar_documento
from app.pipeline.vectorizacion import VectorizadorEmbeddings
from app.rag import cruce
from tests.fakes import EmbeddingsFalsos, subir
from tests.pdfs import pdf_texto
from tests.test_fichas import cima_falsa

MODELO = "gemini-embedding-001"

HISTORIA = (
    "HISTORIA CLINICA\n\nPaciente: Carlos Ruiz Mejia. CC 79.123.456.\n\n"
    "Diagnostico: ulcera gastrica.\n\n"
    "Alergia: penicilina.\n\n"
    "Formula: Ibuprofeno 400 mg. Control en un mes."
)


class LLMCruce:
    """Primera llamada: extrae. Segunda: cruza. Registra lo que recibe."""

    modelo = "falso-cruce"

    def __init__(self, extraer=None, cruzar=None, error=None):
        self.extraer = extraer if extraer is not None else self.extraccion_normal()
        self.cruzar = cruzar
        self.error = error
        self.prompts: list[tuple[str, str]] = []

    @staticmethod
    def extraccion_normal() -> dict:
        return {
            "medicamentos": [
                {
                    "nombre": "Ibuprofeno",
                    "principio_activo": "ibuprofeno",
                    "fragmento": "F1",
                    "extracto_literal": "Ibuprofeno 400 mg",
                },
            ],
            "diagnosticos": [
                {
                    "texto": "úlcera gástrica",
                    "fragmento": "F1",
                    "extracto_literal": "Diagnostico: ulcera gastrica",
                }
            ],
            "alergias": [
                {
                    "texto": "penicilina",
                    "fragmento": "F1",
                    "extracto_literal": "Alergia: penicilina",
                }
            ],
        }

    async def generar_json(self, sistema, prompt, esquema):
        self.prompts.append((sistema, prompt))
        if self.error:
            raise self.error
        if "Lees fragmentos" in sistema:
            return RespuestaLLM(self.extraer, self.modelo)
        assert self.cruzar is not None, "no debió llamarse al comparador"
        return RespuestaLLM(self.cruzar, self.modelo)


@pytest.fixture
def router(app):
    r = EmbeddingRouter({MODELO: EmbeddingsFalsos(MODELO, 1536)})
    app.dependency_overrides[get_router] = lambda: r
    return r


async def _indexar(expediente, router, texto=HISTORIA) -> uuid.UUID:
    r = await subir(
        expediente["id"], pdf_texto([texto]), tipo="HISTORIA_CLINICA", nombre="Historia_Carlos.pdf"
    )
    doc_id = uuid.UUID(r.json()["id"])
    with ThreadPoolExecutor(max_workers=1) as ex:
        await procesar_documento(get_sessionmaker(), doc_id, ex, VectorizadorEmbeddings(router))
    return doc_id


async def _cargar_fichas_ibuprofeno():
    async with cima_falsa([]) as c, get_sessionmaker()() as s:
        await fichas.cargar_fichas(s, c, ["Ibuprofeno"])


async def _cruzar(client, org, expediente, headers=None):
    return await client.post(
        "/internal/v1/cruces",
        headers=org.admin if headers is None else headers,
        json={
            "tenant_id": str(org.tenant_id),
            "expediente_id": expediente["id"],
            "usuario_id": str(org.admin_id),
        },
    )


ADVERTENCIA = {
    "medicamento": "M1",
    "dato": "D1",
    "ficha": "F1",
    "texto": "La ficha de ibuprofeno lo contraindica en pacientes con úlcera gástrica; tu documento menciona úlcera gástrica.",
}


async def test_cruza_el_medicamento_con_el_diagnostico_y_cita_documento_y_ficha(
    client, org_a, cola, router, app
):
    await _cargar_fichas_ibuprofeno()
    llm = LLMCruce(cruzar={"advertencias": [ADVERTENCIA, {**ADVERTENCIA, "ficha": "F9"}]})
    app.dependency_overrides[get_llm] = lambda: llm
    expediente = await org_a.crear_expediente(org_a.admin)
    await _indexar(expediente, router)

    r = await _cruzar(client, org_a, expediente)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["modo"] == "cruce" and not j["sinEvidencia"]
    assert [m["nombre"] for m in j["medicamentos"]] == ["Ibuprofeno"] and j["alergias"][0][
        "texto"
    ] == "penicilina"
    assert len(j["advertencias"]) == 1  # la de la ficha inexistente se descartó
    a = j["advertencias"][0]
    assert a["medicamento"] == "Ibuprofeno" and a["dato"] == "úlcera gástrica" and a["ficha"] == 1
    # una cita al documento a cada lado del cruce y otra a la ficha
    assert j["citas"][a["citaMedicamento"] - 1]["extractoLiteral"] == "Ibuprofeno 400 mg"
    assert "ulcera gastrica" in j["citas"][a["citaDato"] - 1]["extractoLiteral"].lower()
    assert (
        j["fichas"][0]["tipo"] == "FICHA_TECNICA"
        and "úlcera gástrica" in j["fichas"][0]["extractoLiteral"]
    )
    assert any("España" in x for x in j["alertas"]) and any(
        "1 advertencia" in x for x in j["alertas"]
    )
    assert "no indica" in j["avisoGeneral"].lower() or "No indica" in j["avisoGeneral"]
    # lo que salió a la nube iba anonimizado y con las prohibiciones
    for _sistema, prompt in llm.prompts:
        assert (
            "Carlos Ruiz" not in prompt
            and "79.123.456" not in prompt
            and "Historia_Carlos" not in prompt
        )
    assert "PROHIBIDO: recomendar, elegir" in llm.prompts[1][0]


async def test_el_cruce_queda_en_el_historial_sin_el_nombre_del_archivo(
    client, org_a, cola, router, app
):
    await _cargar_fichas_ibuprofeno()
    app.dependency_overrides[get_llm] = lambda: LLMCruce(cruzar={"advertencias": [ADVERTENCIA]})
    expediente = await org_a.crear_expediente(org_a.admin)
    await _indexar(expediente, router)
    await _cruzar(client, org_a, expediente)
    async with get_sessionmaker()() as s:
        fila = (
            await s.scalars(
                select(Consulta).where(Consulta.expediente_id == uuid.UUID(expediente["id"]))
            )
        ).one()
    assert fila.pregunta == "[Cruce de medicamentos]" and fila.respuesta["modo"] == "cruce"


async def test_un_medicamento_sin_ficha_lo_dice_y_remite_sin_llamar_al_comparador(
    client, org_a, cola, router, app
):
    llm = LLMCruce()  # sin fichas cargadas: el comparador no debe llamarse
    app.dependency_overrides[get_llm] = lambda: llm
    expediente = await org_a.crear_expediente(org_a.admin)
    await _indexar(expediente, router)
    j = (await _cruzar(client, org_a, expediente)).json()
    assert j["advertencias"] == [] and j["sinFicha"] == ["Ibuprofeno"] and j["fichas"] == []
    assert any("No hay ficha técnica cargada de: Ibuprofeno" in a for a in j["alertas"])
    assert len(llm.prompts) == 1


async def test_una_advertencia_con_cifras_o_dosis_inventadas_se_descarta(
    client, org_a, cola, router, app
):
    await _cargar_fichas_ibuprofeno()
    inventadas = [
        {
            **ADVERTENCIA,
            "texto": "La ficha advierte no superar 1200 mg al día en pacientes con úlcera gástrica.",
        },
        {**ADVERTENCIA, "texto": "Tu úlcera gástrica es grave, deja de tomarlo."},
        {**ADVERTENCIA, "medicamento": "D1"},  # no es un medicamento
        {**ADVERTENCIA, "dato": "A9"},  # dato inexistente
    ]
    app.dependency_overrides[get_llm] = lambda: LLMCruce(cruzar={"advertencias": inventadas})
    expediente = await org_a.crear_expediente(org_a.admin)
    await _indexar(expediente, router)
    j = (await _cruzar(client, org_a, expediente)).json()
    assert j["advertencias"] == [] and any("4 advertencia" in a for a in j["alertas"])


async def test_sin_medicamentos_en_los_documentos_se_dice(client, org_a, cola, router, app):
    llm = LLMCruce(extraer={"medicamentos": [], "diagnosticos": [], "alergias": []})
    app.dependency_overrides[get_llm] = lambda: llm
    expediente = await org_a.crear_expediente(org_a.admin)
    await _indexar(expediente, router, "INFORME\n\nRadiografia de torax sin alteraciones.")
    j = (await _cruzar(client, org_a, expediente)).json()
    assert (
        j["sinEvidencia"]
        and "No encontré medicamentos" in j["respuestaAnalitica"]
        and len(llm.prompts) == 1
    )


async def test_un_expediente_sin_documentos_indexados_no_llama_al_modelo(
    client, org_a, cola, router, app
):
    llm = LLMCruce()
    app.dependency_overrides[get_llm] = lambda: llm
    expediente = await org_a.crear_expediente(org_a.admin)
    j = (await _cruzar(client, org_a, expediente)).json()
    assert j["sinEvidencia"] and llm.prompts == []


async def test_otro_tenant_no_encuentra_el_expediente_y_un_fallo_del_modelo_es_503(
    client, org_a, org_b, cola, router, app
):
    app.dependency_overrides[get_llm] = lambda: LLMCruce(error=ErrorLLM("sin servicio"))
    expediente = await org_a.crear_expediente(org_a.admin)
    await _indexar(expediente, router)
    assert (await _cruzar(client, org_b, expediente)).status_code == 404
    assert (await _cruzar(client, org_a, expediente)).status_code == 503
    assert (await _cruzar(client, org_a, expediente, headers={})).status_code == 401


def test_un_medicamento_que_el_fragmento_no_escribe_se_descarta():
    from app.rag.busqueda import FragmentoRecuperado

    frag = FragmentoRecuperado(
        id=uuid.uuid4(),
        documento_id=uuid.uuid4(),
        orden=1,
        pagina_inicio=1,
        pagina_fin=1,
        seccion="",
        contenido_texto="Formula: Ibuprofeno 400 mg. Alergia: penicilina.",
        metadata={},
        nombre_archivo="d.pdf",
        tipo_documento="HISTORIA_CLINICA",
        numero_adenda=0,
        sha256_original="0" * 64,
    )
    datos = {
        "medicamentos": [
            {
                "nombre": "Ibuprofeno",
                "principio_activo": "ibuprofeno",
                "fragmento": "F1",
                "extracto_literal": "Ibuprofeno 400 mg",
            },
            {
                "nombre": "Warfarina",
                "principio_activo": "warfarina",
                "fragmento": "F1",
                "extracto_literal": "Warfarina",
            },
        ],
        "diagnosticos": [{"texto": "diabetes", "fragmento": "F1", "extracto_literal": "diabetes"}],
        "alergias": [
            {"texto": "penicilina", "fragmento": "F1", "extracto_literal": "Alergia: penicilina"}
        ],
    }
    _, meds, diags, alergias = cruce.extraer_elementos(datos, [frag], 0.85)
    assert [m["nombre"] for m in meds] == ["Ibuprofeno"] and alergias[0]["texto"] == "penicilina"
    assert (
        diags == []
    )  # un diagnóstico que el fragmento no escribe no se acepta  # el texto del diagnóstico se acota por extracto, no por nombre


def test_el_modelo_puede_escribir_el_id_dentro_del_nombre_y_se_limpia_el_texto():
    meds = [{"nombre": "Ibuprofeno 400 mg", "principio_activo": "ibuprofeno", "cita": 1}]
    diags = [{"texto": "úlcera gástrica", "cita": 2}]
    ficha = [{"texto": "Contraindicado en pacientes con úlcera gástrica activa.", "seccion": "4.3"}]
    datos = {
        "advertencias": [
            {
                "medicamento": "Ibuprofeno 400 mg (M1)",
                "dato": "úlcera gástrica (D1)",
                "ficha": "F1",
                "texto": "La ficha de Ibuprofeno 400 mg (M1) lo contraindica en úlcera gástrica (D1) activa.",
            }
        ]
    }
    adv, omitidas = cruce.ensamblar_advertencias(datos, meds, diags, [], ficha)
    assert omitidas == 0 and len(adv) == 1
    assert "(M1)" not in adv[0]["texto"] and "(D1)" not in adv[0]["texto"]
    assert adv[0]["citaMedicamento"] == 1 and adv[0]["citaDato"] == 2
