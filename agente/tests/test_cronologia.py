"""Línea de tiempo y evolución de resultados: cada dato con su cita, sin interpretar y sin inventar."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest

from app.core.db import get_sessionmaker
from app.ia.embeddings import EmbeddingRouter, get_router
from app.ia.llm import ErrorLLM, RespuestaLLM, get_llm
from app.pipeline.procesador import procesar_documento
from app.pipeline.vectorizacion import VectorizadorEmbeddings
from app.rag import cronologia
from app.rag.busqueda import FragmentoRecuperado
from tests.fakes import EmbeddingsFalsos, subir
from tests.pdfs import pdf_texto

MODELO = "gemini-embedding-001"

LAB_MARZO = (
    "LABORATORIO CLINICO\n\nPaciente: Carlos Ruiz Mejia. CC 79.123.456.\n\nFecha de toma: 12/03/2025\n\n"
    "Hemoglobina 13,2 g/dL (12,0 - 15,5). Colesterol LDL 160 mg/dL ALTO (ref < 130)."
)
LAB_SEPTIEMBRE = (
    "LABORATORIO\n\nFecha: 15 de septiembre de 2025\n\n"
    "Hb 12,1 g/dL (12,0 - 15,5). Control en 3 meses con medicina interna."
)


def _frag(texto: str, documento: uuid.UUID | None = None) -> FragmentoRecuperado:
    return FragmentoRecuperado(
        id=uuid.uuid4(),
        documento_id=documento or uuid.uuid4(),
        orden=1,
        pagina_inicio=1,
        pagina_fin=1,
        seccion="",
        contenido_texto=texto,
        metadata={},
        nombre_archivo="lab.pdf",
        tipo_documento="HISTORIA_CLINICA",
        numero_adenda=0,
        sha256_original="0" * 64,
    )


def _valor(analito, valor, unidad="", rango="", marca="", fecha="", fragmento="F1", extracto=None):
    return {
        "analito": analito,
        "valor": valor,
        "unidad": unidad,
        "rango": rango,
        "marca": marca,
        "fecha_texto": fecha,
        "fragmento": fragmento,
        "extracto_literal": extracto or f"{analito} {valor}",
    }


# ---------- Piezas deterministas ----------
@pytest.mark.parametrize(
    ("texto", "esperada"),
    [
        ("12/03/2025", date(2025, 3, 12)),
        ("12-03-25", date(2025, 3, 12)),
        ("2025-03-12", date(2025, 3, 12)),
        ("15 de septiembre de 2025", date(2025, 9, 15)),
        ("15-sep-2025", date(2025, 9, 15)),
        ("Marzo de 2025", date(2025, 3, 1)),
        ("31/02/2025", None),  # no existe
        ("03/12", None),  # sin año: no se adivina
        ("el martes pasado", None),
    ],
)
def test_las_fechas_las_interpreta_el_codigo_dia_mes_anio(texto, esperada):
    assert cronologia.fecha_desde_texto(texto) == esperada


@pytest.mark.parametrize(
    ("valor", "cifra"),
    [
        ("13,2", 13.2),
        ("13.2", 13.2),
        ("1.020", 1020.0),
        ("250.000", 250000.0),
        ("<5", None),
        ("positivo", None),
    ],
)
def test_las_cifras_se_leen_con_coma_o_punto(valor, cifra):
    assert cronologia._cifra(valor) == cifra


def test_los_sinonimos_agrupan_el_mismo_examen():
    assert (
        cronologia.clave_analito("Hb") == cronologia.clave_analito("Hemoglobina") == "hemoglobina"
    )
    assert cronologia.clave_analito("Colesterol LDL") == cronologia.clave_analito("c-LDL")
    assert cronologia.clave_analito("TGP") == cronologia.clave_analito("ALT")
    assert cronologia.clave_analito("Examen raro") == "examen raro"


def test_agrupa_ordena_y_cita_sin_aceptar_nada_que_el_texto_no_diga():
    doc_a, doc_b = uuid.uuid4(), uuid.uuid4()
    a = _frag(
        "Fecha de toma: 12/03/2025. Hemoglobina 13,2 g/dL (12,0 - 15,5). Colesterol LDL 160 mg/dL ALTO",
        doc_a,
    )
    b = _frag(
        "Fecha: 15 de septiembre de 2025. Hb 12,1 g/dL (12,0 - 15,5). Control en 3 meses.", doc_b
    )
    datos = {
        "eventos": [
            {
                "tipo": "CONTROL",
                "descripcion": "Control en 3 meses",
                "fecha_texto": "15 de septiembre de 2025",
                "fragmento": "F2",
                "extracto_literal": "Control en 3 meses",
            },
            {
                "tipo": "EXAMEN",
                "descripcion": "Laboratorio clínico",
                "fecha_texto": "12/03/2025",
                "fragmento": "F1",
                "extracto_literal": "Fecha de toma: 12/03/2025",
            },
            # sin fecha escrita: no entra a la línea de tiempo
            {
                "tipo": "CONSULTA",
                "descripcion": "Consulta",
                "fecha_texto": "",
                "fragmento": "F1",
                "extracto_literal": "Hemoglobina",
            },
            # juicio que el documento no hace
            {
                "tipo": "EXAMEN",
                "descripcion": "La hemoglobina está baja",
                "fecha_texto": "15 de septiembre de 2025",
                "fragmento": "F2",
                "extracto_literal": "Hb 12,1",
            },
        ],  # fmt: skip
        "valores": [
            _valor(
                "Hb",
                "12,1",
                "g/dL",
                "12,0 - 15,5",
                fecha="15 de septiembre de 2025",
                fragmento="F2",
            ),
            _valor(
                "Hemoglobina", "13,2", "g/dL", "12,0 - 15,5", "ALTO", fecha="12/03/2025"
            ),  # marca no impresa
            _valor("Colesterol LDL", "160", "mg/dL", "", "ALTO", fecha="12/03/2025"),
            _valor("Glucosa", "98", "mg/dL", fecha="12/03/2025"),  # inventado: no está en el texto
            _valor("Hemoglobina", "13,2", "mmol/L", fecha="12/03/2025"),  # unidad inventada
            _valor("Hemoglobina", "13,2", "g/dL", "10 - 20", fecha="12/03/2025"),  # rango inventado
            _valor(
                "Hemoglobina", "13,2", "g/dL", fecha="01/01/2020"
            ),  # fecha que el documento no escribe
        ],
    }
    citas, eventos, analitos, descartados = cronologia.ensamblar(datos, [a, b], 0.85)

    # ordenados por fecha; la toma de septiembre entra como evento armado con sus valores comprobados
    assert [e["fecha"] for e in eventos] == ["2025-03-12", "2025-09-15", "2025-09-15"]
    assert [e["tipo"] for e in eventos] == ["EXAMEN", "CONTROL", "EXAMEN"]
    assert eventos[2]["texto"] == "Resultados de laboratorio: Hb."
    assert all("_doc" not in e for e in eventos)
    hb = next(g for g in analitos if g["clave"] == "hemoglobina")
    assert [v["valor"] for v in hb["valores"]] == [13.2, 12.1] and hb["comparable"]
    assert [v["fecha"] for v in hb["valores"]] == ["2025-03-12", "2025-09-15"]
    assert hb["valores"][0]["marca"] is None  # el modelo dijo ALTO, pero el documento no lo marca
    assert hb["valores"][0]["rango"] == "12,0 - 15,5"
    ldl = next(g for g in analitos if g["clave"] == "colesterol ldl")
    assert ldl["valores"][0]["marca"] == "ALTO"
    assert not any(g["clave"] == "glucosa" for g in analitos)
    # la fecha inventada no se acepta y el valor repetido no se duplica: queda el de la fecha escrita
    assert all(v["fecha"] for v in hb["valores"])
    assert descartados == 5  # 2 eventos y 3 valores (glucosa, unidad y rango inventados)
    for e in eventos:
        assert citas.lista[e["cita"] - 1].extracto


def test_un_control_relativo_se_ubica_junto_al_documento_que_lo_indica_sin_calcular_su_fecha():
    a = _frag("Fecha de toma: 15/09/2025. Hb 12,1 g/dL. Control en 3 meses con medicina interna.")
    datos = {
        "eventos": [
            {
                "tipo": "CONTROL",
                "descripcion": "Control en 3 meses con medicina interna",
                "fecha_texto": "en 3 meses",
                "fragmento": "F1",
                "extracto_literal": "Control en 3 meses con medicina interna",
            }
        ],
        "valores": [_valor("Hb", "12,1", "g/dL", fecha="15/09/2025")],
    }
    _, eventos, _, _ = cronologia.ensamblar(datos, [a], 0.85)
    control = next(e for e in eventos if e["tipo"] == "CONTROL")
    assert control["fecha"] is None and control["fechaTexto"] == "en 3 meses"
    assert (
        control["referencia"] == "2025-09-15"
    )  # el documento que lo indica, no la fecha del control


def test_unidades_distintas_no_se_grafican_juntas():
    a = _frag("12/03/2025 Glucosa 5,5 mmol/L")
    b = _frag("15/09/2025 Glucosa 99 mg/dL")
    datos = {
        "eventos": [],
        "valores": [
            _valor("Glucosa", "5,5", "mmol/L", fecha="12/03/2025"),
            _valor("Glucosa", "99", "mg/dL", fecha="15/09/2025", fragmento="F2"),
        ],
    }
    _, _, analitos, _ = cronologia.ensamblar(datos, [a, b], 0.85)
    assert analitos[0]["unidades"] == ["mmol/L", "mg/dL"] and analitos[0]["comparable"] is False


# ---------- Por la API interna ----------
class LLMCronologia:
    modelo = "falso-cronologia"

    def __init__(self, datos=None, error=None):
        self.datos = datos if datos is not None else self.normal()
        self.error = error
        self.prompts: list[tuple[str, str]] = []

    @staticmethod
    def normal() -> dict:
        return {
            "eventos": [
                {
                    "tipo": "CONTROL",
                    "descripcion": "Control en 3 meses con medicina interna",
                    "fecha_texto": "15 de septiembre de 2025",
                    "fragmento": "F2",
                    "extracto_literal": "Control en 3 meses con medicina interna",
                }
            ],
            "valores": [
                _valor("Hemoglobina", "13,2", "g/dL", "12,0 - 15,5", fecha="12/03/2025"),
                _valor(
                    "Hb",
                    "12,1",
                    "g/dL",
                    "12,0 - 15,5",
                    fecha="15 de septiembre de 2025",
                    fragmento="F2",
                ),
            ],
        }

    async def generar_json(self, sistema, prompt, esquema):
        self.prompts.append((sistema, prompt))
        if self.error:
            raise self.error
        return RespuestaLLM(self.datos, self.modelo)


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


async def _pedir(client, org, expediente, headers=None, rehacer=False):
    return await client.post(
        "/internal/v1/cronologias",
        headers=org.admin if headers is None else headers,
        json={
            "tenant_id": str(org.tenant_id),
            "expediente_id": expediente["id"],
            "usuario_id": str(org.admin_id),
            "rehacer": rehacer,
        },
    )


async def test_arma_la_linea_de_tiempo_con_citas_y_la_reutiliza_si_nada_cambio(
    client, org_a, cola, router, app
):
    llm = LLMCronologia()
    app.dependency_overrides[get_llm] = lambda: llm
    expediente = await org_a.crear_expediente(org_a.admin)
    await _indexar(expediente, router, LAB_MARZO, "Lab_Carlos_marzo.pdf")
    await _indexar(expediente, router, LAB_SEPTIEMBRE, "Lab_Carlos_sept.pdf")

    r = await _pedir(client, org_a, expediente)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["modo"] == "cronologia" and not j["sinEvidencia"] and j["guardada"] is False
    hb = j["analitos"][0]
    assert hb["clave"] == "hemoglobina" and [v["valor"] for v in hb["valores"]] == [13.2, 12.1]
    assert [e["tipo"] for e in j["eventos"]] == ["EXAMEN", "CONTROL", "EXAMEN"]
    control = next(e for e in j["eventos"] if e["tipo"] == "CONTROL")
    assert control["fecha"] == "2025-09-15"
    assert j["citas"][hb["valores"][0]["cita"] - 1]["extractoLiteral"]
    assert "No interpreta" in j["avisoGeneral"] or "no interpreta" in j["avisoGeneral"].lower()
    # a la nube fue anonimizado y sin el nombre del archivo
    _, prompt = llm.prompts[0]
    assert "Carlos Ruiz" not in prompt and "79.123.456" not in prompt and "Lab_Carlos" not in prompt

    # sin documentos nuevos: la misma, sin llamar al modelo
    j2 = (await _pedir(client, org_a, expediente)).json()
    assert j2["guardada"] is True and j2["huella"] == j["huella"] and len(llm.prompts) == 1
    # «rehacer» la vuelve a armar
    assert (await _pedir(client, org_a, expediente, rehacer=True)).json()["guardada"] is False
    assert len(llm.prompts) == 2
    # un documento nuevo cambia la huella: se vuelve a armar
    await _indexar(expediente, router, "EPICRISIS\n\nEgreso 20/10/2025.", "Epicrisis.pdf")
    j3 = (await _pedir(client, org_a, expediente)).json()
    assert j3["guardada"] is False and j3["huella"] != j["huella"] and len(llm.prompts) == 3


async def test_sin_documentos_no_llama_al_modelo(client, org_a, cola, router, app):
    llm = LLMCronologia()
    app.dependency_overrides[get_llm] = lambda: llm
    expediente = await org_a.crear_expediente(org_a.admin)
    j = (await _pedir(client, org_a, expediente)).json()
    assert (
        j["sinEvidencia"] and "No encontré fechas" in j["respuestaAnalitica"] and llm.prompts == []
    )


async def test_otro_tenant_no_la_ve_y_un_fallo_del_modelo_es_503(
    client, org_a, org_b, cola, router, app
):
    app.dependency_overrides[get_llm] = lambda: LLMCronologia(error=ErrorLLM("sin servicio"))
    expediente = await org_a.crear_expediente(org_a.admin)
    await _indexar(expediente, router, LAB_MARZO, "Lab.pdf")
    assert (await _pedir(client, org_b, expediente)).status_code == 404
    assert (await _pedir(client, org_a, expediente)).status_code == 503
    assert (await _pedir(client, org_a, expediente, headers={})).status_code == 401


def test_los_controles_sin_fecha_se_conservan_con_su_plazo_o_sin_fecha():
    """El modelo suele devolver «control en 3 meses» sin fecha: no se pierde de la línea ni de los recordatorios."""
    a = _frag("Fecha: 15/09/2025. Hb 12,1 g/dL. Control en 3 meses. Control con cardiologia.")
    sin_fecha = {"fecha_texto": "", "fragmento": "F1"}
    datos = {
        "eventos": [
            {
                **sin_fecha,
                "tipo": "CONTROL",
                "descripcion": "Control en 3 meses",
                "extracto_literal": "Control en 3 meses",
            },
            {
                **sin_fecha,
                "tipo": "CONTROL",
                "descripcion": "Control con cardiologia",
                "extracto_literal": "Control con cardiologia",
            },
            {
                **sin_fecha,
                "tipo": "CONSULTA",
                "descripcion": "Consulta",
                "extracto_literal": "Hb 12,1",
            },
        ],
        "valores": [_valor("Hb", "12,1", "g/dL", fecha="15/09/2025")],
    }
    _, eventos, _, descartados = cronologia.ensamblar(datos, [a], 0.85)
    controles = {e["texto"]: e for e in eventos if e["tipo"] == "CONTROL"}
    assert controles["Control en 3 meses"]["fechaTexto"] == "en 3 meses"
    assert controles["Control con cardiologia"]["fechaTexto"] == cronologia.SIN_FECHA_ESCRITA
    assert all(c["referencia"] == "2025-09-15" for c in controles.values())
    assert descartados == 1  # la consulta sin fecha sí se descarta
