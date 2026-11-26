"""Propuestas de recordatorio: la fecha la calcula el código, cada una con su cita y nunca de una toma."""

from datetime import date

import pytest

from app.ia.embeddings import EmbeddingRouter, get_router
from app.ia.llm import get_llm
from app.rag import recordatorios
from tests.fakes import EmbeddingsFalsos
from tests.test_cronologia import LAB_SEPTIEMBRE, MODELO, LLMCronologia, _indexar


@pytest.fixture
def router(app):
    r = EmbeddingRouter({MODELO: EmbeddingsFalsos(MODELO, 1536)})
    app.dependency_overrides[get_router] = lambda: r
    return r


@pytest.mark.parametrize(
    ("texto", "esperada"),
    [
        ("Control en 3 meses", date(2025, 12, 15)),
        ("control dentro de 15 días", date(2025, 9, 30)),
        ("cita en dos semanas", date(2025, 9, 29)),
        ("control en un año", date(2026, 9, 15)),
        ("Control con medicina interna", None),  # sin plazo: la persona pone la fecha
    ],
)
def test_el_plazo_se_cuenta_desde_la_fecha_del_documento(texto, esperada):
    assert recordatorios.fecha_por_plazo(texto, date(2025, 9, 15)) == esperada


def test_fin_de_mes_no_se_sale_del_calendario():
    assert recordatorios.fecha_por_plazo("en 1 mes", date(2026, 1, 31)) == date(2026, 2, 28)


CITAS = [
    {
        "documentoId": "d1",
        "nombreArchivo": "lab.pdf",
        "paginaInicio": 1,
        "extractoLiteral": "Control en 3 meses con medicina interna",
    },
    {
        "documentoId": "d2",
        "nombreArchivo": "formula.pdf",
        "paginaInicio": 1,
        "extractoLiteral": "Atorvastatina 20 mg cada noche",
    },
    {
        "documentoId": "d3",
        "nombreArchivo": "orden.pdf",
        "paginaInicio": 2,
        "extractoLiteral": "Cita el 12/02/2026",
    },
]


def _ev(texto, cita, fecha=None, referencia=None, fecha_texto="", tipo="CONTROL"):
    return {
        "tipo": tipo,
        "texto": texto,
        "cita": cita,
        "fecha": fecha,
        "referencia": referencia,
        "fechaTexto": fecha_texto,
    }


def test_propone_los_controles_con_su_cita_y_nunca_una_toma():
    linea = {
        "citas": CITAS,
        "eventos": [
            _ev(
                "Control en 3 meses con medicina interna",
                1,
                referencia="2025-09-15",
                fecha_texto="en 3 meses",
            ),
            # el modelo puso la fecha del documento como fecha del control: el plazo se cuenta desde ella
            _ev(
                "Control en 3 meses con medicina interna",
                1,
                fecha="2025-09-15",
                fecha_texto="15/09/2025",
            ),
            _ev(
                "Tomar atorvastatina cada noche",
                2,
                referencia="2025-09-15",
                fecha_texto="cada noche",
            ),
            _ev("Cita el 12/02/2026", 3, fecha="2026-02-12", fecha_texto="12/02/2026"),
            _ev("Examen de laboratorio", 1, fecha="2025-09-15", tipo="EXAMEN"),
        ],
    }
    p = recordatorios.propuestas(linea)
    assert [x["texto"] for x in p] == [
        "Control en 3 meses con medicina interna",
        "Cita el 12/02/2026",
    ]
    assert p[0]["fechaPropuesta"] == "2025-12-15" and p[0]["fechaDocumento"] == "2025-09-15"
    assert p[1]["fechaPropuesta"] == "2026-02-12"
    assert p[0]["cita"] == {
        "documentoId": "d1",
        "nombreArchivo": "lab.pdf",
        "paginaInicio": 1,
        "extractoLiteral": "Control en 3 meses con medicina interna",
    }


async def test_el_endpoint_propone_desde_la_linea_de_tiempo_guardada(
    client, org_a, cola, router, app
):
    control = {
        "tipo": "CONTROL",
        "descripcion": "Control en 3 meses con medicina interna",
        "fecha_texto": "en 3 meses",
        "fragmento": "F1",
        "extracto_literal": "Control en 3 meses con medicina interna",
    }
    valor = {
        "analito": "Hb", "valor": "12,1", "unidad": "g/dL", "rango": "", "marca": "",
        "fecha_texto": "15 de septiembre de 2025", "fragmento": "F1", "extracto_literal": "Hb 12,1 g/dL",
    }  # fmt: skip
    llm = LLMCronologia(datos={"eventos": [control], "valores": [valor]})
    app.dependency_overrides[get_llm] = lambda: llm
    expediente = await org_a.crear_expediente(org_a.admin)
    await _indexar(expediente, router, LAB_SEPTIEMBRE, "Lab.pdf")
    cuerpo = {
        "tenant_id": str(org_a.tenant_id),
        "expediente_id": expediente["id"],
        "usuario_id": str(org_a.admin_id),
    }

    r = await client.post("/internal/v1/recordatorios/propuestas", headers=org_a.admin, json=cuerpo)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["lineaGuardada"] is False and len(j["propuestas"]) == 1
    p = j["propuestas"][0]
    assert p["texto"].startswith("Control en 3 meses") and p["fechaPropuesta"] == "2025-12-15"
    assert p["cita"]["extractoLiteral"]
    # la segunda vez usa la línea guardada: sin llamar al modelo
    j2 = (
        await client.post("/internal/v1/recordatorios/propuestas", headers=org_a.admin, json=cuerpo)
    ).json()
    assert j2["lineaGuardada"] is True and len(llm.prompts) == 1
