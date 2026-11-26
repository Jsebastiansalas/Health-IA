"""«Preparar mi cita»: resumen con cita en cada dato y preguntas que no afirman, no recetan ni dosifican."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.ia.embeddings import EmbeddingRouter, get_router
from app.ia.llm import ErrorLLM, RespuestaLLM, get_llm
from app.models import Consulta
from app.pipeline.procesador import procesar_documento
from app.pipeline.vectorizacion import VectorizadorEmbeddings
from app.rag import preparacion
from tests.fakes import EmbeddingsFalsos, subir
from tests.pdfs import pdf_texto
from tests.test_cronologia import LAB_MARZO, LAB_SEPTIEMBRE, LLMCronologia

MODELO = "gemini-embedding-001"
FORMULA = (
    "FORMULA MEDICA\n\nPaciente: Carlos Ruiz Mejia. CC 79.123.456.\n\nFecha: 15/09/2025\n\n"
    "Diagnostico: dislipidemia.\n\nAtorvastatina 20 mg."
)
FUENTES = [LAB_MARZO, LAB_SEPTIEMBRE, FORMULA]


# ---------- Preguntas ----------
def test_solo_quedan_preguntas_que_no_afirman_recetan_ni_dosifican():
    propuestas = [
        "¿Qué significa que el colesterol LDL salga marcado como ALTO?",
        "Debo seguir con la atorvastatina",  # no es pregunta
        "¿Debo tomar 40 mg cada 12 horas?",  # posología sin respaldo
        "¿Es preocupante que la hemoglobina esté baja?",  # juicio que el documento no hace
        "¿Tienes diabetes?",  # afirma un diagnóstico
        "¿Es normal un valor de 250?",  # cifra que no está en los documentos
        "¿Cuándo debo repetir el perfil lipídico?",
        "¿cuándo debo repetir el perfil lipídico?",  # repetida
        "¿Por qué bajó la hemoglobina de 13,2 a 12,1?",  # cifras que sí están
    ]
    assert preparacion.validar_preguntas(propuestas, FUENTES) == [
        "¿Qué significa que el colesterol LDL salga marcado como ALTO?",
        "¿Cuándo debo repetir el perfil lipídico?",
        "¿Por qué bajó la hemoglobina de 13,2 a 12,1?",
    ]


def test_una_pregunta_con_contexto_conserva_su_unico_signo_de_apertura():
    q = preparacion.validar_preguntas(
        ["El colesterol LDL salió marcado ALTO, ¿cómo ha evolucionado?"], FUENTES
    )
    assert q == ["El colesterol LDL salió marcado ALTO, ¿cómo ha evolucionado?"]


def test_maximo_seis_preguntas_y_se_completa_el_signo_de_apertura():
    q = preparacion.validar_preguntas(
        [f"Pregunta número {i} sobre el examen?" for i in range(10)], ["número 0 1 2 3 4 5 6 7 8 9"]
    )
    assert len(q) == 6 and all(x.startswith("¿") and x.endswith("?") for x in q)


def test_los_cambios_son_el_primero_y_el_ultimo_valor_fechado():
    linea = {
        "analitos": [
            {
                "nombre": "Hemoglobina",
                "comparable": True,
                "valores": [
                    {
                        "fecha": "2025-03-12",
                        "valorTexto": "13,2",
                        "unidad": "g/dL",
                        "marca": None,
                        "cita": 1,
                    },
                    {
                        "fecha": None,
                        "valorTexto": "12,8",
                        "unidad": "g/dL",
                        "marca": None,
                        "cita": 2,
                    },
                    {
                        "fecha": "2025-09-15",
                        "valorTexto": "12,1",
                        "unidad": "g/dL",
                        "marca": None,
                        "cita": 3,
                    },
                ],
            },
            {
                "nombre": "LDL",
                "comparable": True,
                "valores": [{"fecha": "2025-03-12", "valorTexto": "160", "cita": 4}],
            },
            {
                "nombre": "Glucosa",
                "comparable": False,
                "valores": [
                    {"fecha": "2025-03-12", "valorTexto": "5,5"},
                    {"fecha": "2025-09-15", "valorTexto": "99"},
                ],
            },
        ]
    }
    cambios = preparacion.cambios_de(linea)
    assert (
        len(cambios) == 1
        and cambios[0]["nombre"] == "Hemoglobina"
        and cambios[0]["mediciones"] == 2
    )
    assert (
        cambios[0]["desde"]["valorTexto"] == "13,2" and cambios[0]["hasta"]["valorTexto"] == "12,1"
    )


# ---------- Por la API interna ----------
class LLMPreparacion(LLMCronologia):
    """Responde a la línea de tiempo y a la preparación según el sistema que recibe."""

    def __init__(self, preparar=None, error=None):
        super().__init__(error=error)
        self.preparar = preparar if preparar is not None else self.preparacion_normal()

    @staticmethod
    def preparacion_normal() -> dict:
        return {
            "medicamentos": [
                {
                    "nombre": "Atorvastatina",
                    "principio_activo": "atorvastatina",
                    "fragmento": "F3",
                    "extracto_literal": "Atorvastatina 20 mg",
                }
            ],
            "diagnosticos": [
                {
                    "texto": "dislipidemia",
                    "fragmento": "F3",
                    "extracto_literal": "Diagnostico: dislipidemia",
                }
            ],
            "alergias": [],
            "preguntas": [
                "¿Qué significa que el colesterol LDL salga marcado como ALTO?",
                "¿Debo tomar 40 mg de atorvastatina cada noche?",
                "¿Cuándo debo repetir el perfil lipídico?",
            ],
        }

    async def generar_json(self, sistema, prompt, esquema):
        if "PREGUNTAS" in sistema:
            self.prompts.append((sistema, prompt))
            if self.error:
                raise self.error
            return RespuestaLLM(self.preparar, self.modelo)
        return await super().generar_json(sistema, prompt, esquema)


@pytest.fixture
def router(app):
    r = EmbeddingRouter({MODELO: EmbeddingsFalsos(MODELO, 1536)})
    app.dependency_overrides[get_router] = lambda: r
    return r


async def _indexar(expediente, router, texto, nombre) -> uuid.UUID:
    r = await subir(expediente["id"], pdf_texto([texto]), tipo="HISTORIA_CLINICA", nombre=nombre)
    doc_id = uuid.UUID(r.json()["id"])
    with ThreadPoolExecutor(max_workers=1) as ex:
        await procesar_documento(get_sessionmaker(), doc_id, ex, VectorizadorEmbeddings(router))
    return doc_id


async def _preparar(client, org, expediente, headers=None):
    return await client.post(
        "/internal/v1/preparaciones",
        headers=org.admin if headers is None else headers,
        json={
            "tenant_id": str(org.tenant_id),
            "expediente_id": expediente["id"],
            "usuario_id": str(org.admin_id),
        },
    )


async def test_prepara_la_cita_con_citas_y_reutiliza_la_linea_de_tiempo(
    client, org_a, cola, router, app
):
    llm = LLMPreparacion()
    app.dependency_overrides[get_llm] = lambda: llm
    expediente = await org_a.crear_expediente(org_a.admin)
    await _indexar(expediente, router, LAB_MARZO, "Lab_marzo.pdf")
    await _indexar(expediente, router, LAB_SEPTIEMBRE, "Lab_sept.pdf")
    await _indexar(expediente, router, FORMULA, "Formula_Carlos.pdf")

    r = await _preparar(client, org_a, expediente)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["modo"] == "preparacion" and not j["sinEvidencia"] and j["generadaAt"]
    assert "No es un diagnóstico" in j["avisoGeneral"]
    hb = next(c for c in j["cambios"] if c["nombre"] == "Hemoglobina")
    assert hb["desde"]["valorTexto"] == "13,2" and hb["hasta"]["valorTexto"] == "12,1"
    assert (
        j["eventos"] and j["eventos"][0]["fecha"] >= j["eventos"][-1]["fecha"]
    )  # lo más reciente primero
    # las citas de la extracción van después de las de la línea de tiempo y apuntan al texto correcto
    med = j["medicamentos"][0]
    assert (
        med["nombre"] == "Atorvastatina"
        and j["citas"][med["cita"] - 1]["extractoLiteral"] == "Atorvastatina 20 mg"
    )
    assert j["citas"][hb["desde"]["cita"] - 1]["extractoLiteral"]
    assert j["diagnosticos"][0]["texto"] == "dislipidemia"
    # la pregunta con una dosis que ningún documento dice se descarta
    assert j["preguntas"] == [
        "¿Qué significa que el colesterol LDL salga marcado como ALTO?",
        "¿Cuándo debo repetir el perfil lipídico?",
    ]
    assert any("1 pregunta" in a for a in j["alertas"])
    # a la nube fue anonimizado
    for _s, prompt in llm.prompts:
        assert (
            "Carlos Ruiz" not in prompt
            and "79.123.456" not in prompt
            and "Formula_Carlos" not in prompt
        )
    assert len(llm.prompts) == 2  # línea de tiempo + preparación

    # queda en el historial; la segunda vez la línea de tiempo sale guardada (una sola llamada más)
    await _preparar(client, org_a, expediente)
    assert len(llm.prompts) == 3
    async with get_sessionmaker()() as s:
        preguntas = (
            await s.scalars(
                select(Consulta.pregunta).where(
                    Consulta.expediente_id == uuid.UUID(expediente["id"])
                )
            )
        ).all()
    assert preguntas.count("[Preparar mi cita]") == 2 and preguntas.count("[Línea de tiempo]") == 1


async def test_sin_documentos_no_llama_al_modelo(client, org_a, cola, router, app):
    llm = LLMPreparacion()
    app.dependency_overrides[get_llm] = lambda: llm
    expediente = await org_a.crear_expediente(org_a.admin)
    j = (await _preparar(client, org_a, expediente)).json()
    assert (
        j["sinEvidencia"]
        and "Todavía no hay documentos" in j["respuestaAnalitica"]
        and llm.prompts == []
    )


async def test_otro_tenant_no_la_ve_y_un_fallo_del_modelo_es_503(
    client, org_a, org_b, cola, router, app
):
    app.dependency_overrides[get_llm] = lambda: LLMPreparacion(error=ErrorLLM("sin servicio"))
    expediente = await org_a.crear_expediente(org_a.admin)
    await _indexar(expediente, router, LAB_MARZO, "Lab.pdf")
    assert (await _preparar(client, org_b, expediente)).status_code == 404
    assert (await _preparar(client, org_a, expediente)).status_code == 503
    assert (await _preparar(client, org_a, expediente, headers={})).status_code == 401
