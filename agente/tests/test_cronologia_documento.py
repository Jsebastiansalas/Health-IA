"""La línea de tiempo se extrae una vez por documento, se guarda cifrada y se arma sin el modelo."""

import re
import uuid

import psycopg
import pytest

from app.core.config import get_settings
from app.ia.embeddings import EmbeddingRouter, get_router
from app.ia.llm import ErrorLLM, RespuestaLLM, get_llm
from app.rag import extraccion_linea
from tests.conftest import interno
from tests.fakes import EmbeddingsFalsos
from tests.test_cronologia import MODELO, _indexar, _pedir


@pytest.fixture
def router(app):
    r = EmbeddingRouter({MODELO: EmbeddingsFalsos(MODELO, 1536)})
    app.dependency_overrides[get_router] = lambda: r
    return r


class LLMPorFragmento:
    """Devuelve un valor de glucosa por cada fragmento del prompt que lo traiga: así lo que sale en
    la línea depende de lo que de verdad se le envió al modelo."""

    modelo = "falso-por-fragmento"

    def __init__(self, fallar_si: str = ""):
        self.fallar_si = fallar_si
        self.prompts: list[str] = []

    async def generar_json(self, sistema, prompt, esquema):
        self.prompts.append(prompt)
        if self.fallar_si and self.fallar_si in prompt:
            raise ErrorLLM("sin servicio")
        valores = []
        # Cada fragmento del prompt empieza por su id («F1», «F2»…).
        partes = re.split(r"(?<![A-Za-z0-9])(F\d+)(?![A-Za-z0-9])", prompt)
        for ident, cuerpo in zip(partes[1::2], partes[2::2], strict=False):
            for m in re.finditer(r"Fecha: (\d\d/\d\d/\d{4})\. Glucosa (\d+) mg/dL", cuerpo):
                valores.append(
                    {
                        "analito": "Glucosa",
                        "valor": m[2],
                        "unidad": "mg/dL",
                        "rango": "",
                        "marca": "",
                        "fecha_texto": m[1],
                        "fragmento": ident,
                        "extracto_literal": m[0],
                    }
                )
        return RespuestaLLM({"eventos": [], "valores": valores}, self.modelo)


def _lab(dia: int, valor: int) -> str:
    return f"LABORATORIO\n\nFecha: {dia:02d}/03/2025. Glucosa {valor} mg/dL."


def _usar(app, llm):
    app.dependency_overrides[get_llm] = lambda: llm
    return llm


def _valores(cuerpo: dict) -> list[float]:
    return [v["valor"] for a in cuerpo["analitos"] for v in a["valores"]]


def _filas(postgres_url: str, sql: str, *args) -> list[tuple]:
    with psycopg.connect(postgres_url) as conn:
        return conn.execute(sql, args).fetchall()


async def _extraer(client, org, expediente, documento_id, headers=None):
    return await client.post(
        f"/internal/v1/documentos/{documento_id}/linea",
        headers=interno() if headers is None else headers,
        json={"tenant_id": str(org.tenant_id), "expediente_id": expediente["id"]},
    )


@pytest.fixture
def personal(org_a, postgres_url):
    with psycopg.connect(postgres_url) as conn:
        conn.execute("UPDATE tenants SET tipo = 'PERSONAL' WHERE id = %s", (org_a.tenant_id,))
    return org_a


async def test_al_indexar_se_extrae_y_abrir_la_linea_ya_no_llama_al_modelo(
    client, personal, cola, router, app, postgres_url
):
    llm = _usar(app, LLMPorFragmento())
    expediente = await personal.crear_expediente()
    a = await _indexar(expediente, router, _lab(1, 91), "a.pdf")
    b = await _indexar(expediente, router, _lab(2, 102), "b.pdf")
    for doc in (a, b):
        r = await _extraer(client, personal, expediente, doc)
        assert r.status_code == 200, r.text
        assert r.json() == {"estado": "extraida"}
    assert len(llm.prompts) == 2

    j = (await _pedir(client, personal, expediente)).json()
    assert _valores(j) == [91.0, 102.0] and len(llm.prompts) == 2
    assert j["modeloLlm"] == llm.modelo and j["guardada"] is False
    assert all(j["citas"][v["cita"] - 1]["extractoLiteral"] for v in j["analitos"][0]["valores"])

    # pedirlo otra vez no vuelve a gastar
    assert (await _extraer(client, personal, expediente, a)).json() == {"estado": "ya_estaba"}
    assert len(llm.prompts) == 2


async def test_lo_extraido_se_guarda_cifrado(client, personal, cola, router, app, postgres_url):
    _usar(app, LLMPorFragmento())
    expediente = await personal.crear_expediente()
    doc = await _indexar(expediente, router, _lab(1, 91), "a.pdf")
    await _extraer(client, personal, expediente, doc)
    [(crudo,)] = _filas(postgres_url, "SELECT datos::text FROM extracciones_linea")
    assert "mtd1:" in crudo and "Glucosa" not in crudo and "91" not in crudo.split("mtd1:")[0]


async def test_un_expediente_largo_no_se_corta(client, org_a, cola, router, app, monkeypatch):
    monkeypatch.setattr(get_settings(), "cronologia_max_fragmentos", 2)
    llm = _usar(app, LLMPorFragmento())
    expediente = await org_a.crear_expediente()
    for dia in range(1, 8):
        await _indexar(expediente, router, _lab(dia, 80 + dia), f"{dia}.pdf")

    j = (await _pedir(client, org_a, expediente)).json()
    assert sorted(_valores(j)) == [float(80 + d) for d in range(1, 8)]
    assert len(llm.prompts) == 4  # 7 fragmentos en tandas de 2
    assert not any("primeros fragmentos" in a for a in j["alertas"])
    assert j["fragmentosRecuperados"] == 7 and j["documentos"] == 7


async def test_solo_se_envia_al_modelo_el_documento_nuevo(client, org_a, cola, router, app):
    llm = _usar(app, LLMPorFragmento())
    expediente = await org_a.crear_expediente()
    await _indexar(expediente, router, _lab(1, 91), "a.pdf")
    await _pedir(client, org_a, expediente)
    await _indexar(expediente, router, _lab(2, 102), "b.pdf")

    j = (await _pedir(client, org_a, expediente)).json()
    assert _valores(j) == [91.0, 102.0] and len(llm.prompts) == 2
    assert "Glucosa 102" in llm.prompts[1] and "Glucosa 91" not in llm.prompts[1]


async def test_rehacer_vuelve_a_leer_todos_los_documentos(client, org_a, cola, router, app):
    llm = _usar(app, LLMPorFragmento())
    expediente = await org_a.crear_expediente()
    await _indexar(expediente, router, _lab(1, 91), "a.pdf")
    await _pedir(client, org_a, expediente)
    await _pedir(client, org_a, expediente, rehacer=True)
    assert len(llm.prompts) == 2


async def test_si_cambian_las_instrucciones_se_vuelve_a_extraer(
    client, org_a, cola, router, app, monkeypatch
):
    llm = _usar(app, LLMPorFragmento())
    expediente = await org_a.crear_expediente()
    await _indexar(expediente, router, _lab(1, 91), "a.pdf")
    primera = (await _pedir(client, org_a, expediente)).json()
    monkeypatch.setattr(extraccion_linea, "VERSION", "otra-version")

    segunda = (await _pedir(client, org_a, expediente)).json()
    assert segunda["guardada"] is False and segunda["huella"] != primera["huella"]
    assert len(llm.prompts) == 2


async def test_si_cambian_los_fragmentos_se_vuelve_a_extraer(
    client, org_a, cola, router, app, postgres_url
):
    llm = _usar(app, LLMPorFragmento())
    expediente = await org_a.crear_expediente()
    await _indexar(expediente, router, _lab(1, 91), "a.pdf")
    await _pedir(client, org_a, expediente)
    with psycopg.connect(postgres_url) as conn:
        conn.execute("UPDATE fragmentos SET id = uuid_generate_v4()")

    j = (await _pedir(client, org_a, expediente, rehacer=False)).json()
    # la línea guardada sigue valiendo (mismos documentos); al rehacerla no usa lo caducado
    assert j["guardada"] is True
    with psycopg.connect(postgres_url) as conn:
        conn.execute("DELETE FROM consultas")
    j2 = (await _pedir(client, org_a, expediente)).json()
    assert _valores(j2) == [91.0] and len(llm.prompts) == 2


async def test_un_fallo_parcial_se_avisa_y_se_reintenta_solo_lo_que_falta(
    client, org_a, cola, router, app, monkeypatch
):
    monkeypatch.setattr(get_settings(), "cronologia_max_fragmentos", 1)
    llm = _usar(app, LLMPorFragmento(fallar_si="Glucosa 102"))
    expediente = await org_a.crear_expediente()
    await _indexar(expediente, router, _lab(1, 91), "a.pdf")
    await _indexar(expediente, router, _lab(2, 102), "b.pdf")

    j = (await _pedir(client, org_a, expediente)).json()
    assert _valores(j) == [91.0]
    assert any("1 documento" in a and "vuelve a intentarlo" in a.lower() for a in j["alertas"])

    llm.fallar_si = ""
    antes = len(llm.prompts)
    j2 = (await _pedir(client, org_a, expediente)).json()
    assert j2["guardada"] is False, "una línea incompleta no se reutiliza"
    assert _valores(j2) == [91.0, 102.0] and len(llm.prompts) == antes + 1


async def test_un_documento_muy_largo_se_limita_y_se_avisa(
    client, org_a, cola, router, app, monkeypatch
):
    monkeypatch.setattr(get_settings(), "cronologia_max_fragmentos_documento", 1)
    _usar(app, LLMPorFragmento())
    expediente = await org_a.crear_expediente()
    relleno = "\n\n".join(
        f"RESULTADOS {i}\n\n" + ("Texto de relleno del informe de laboratorio. " * 120)
        for i in range(4)
    )
    await _indexar(expediente, router, _lab(1, 91) + "\n\n" + relleno, "largo.pdf")
    j = (await _pedir(client, org_a, expediente)).json()
    assert j["fragmentosRecuperados"] == 1
    assert any("muy largo" in a for a in j["alertas"])


async def test_borrar_el_documento_borra_lo_extraido(
    client, org_a, cola, router, app, postgres_url
):
    _usar(app, LLMPorFragmento())
    expediente = await org_a.crear_expediente()
    doc = await _indexar(expediente, router, _lab(1, 91), "a.pdf")
    await _pedir(client, org_a, expediente)
    assert _filas(postgres_url, "SELECT count(*) FROM extracciones_linea") == [(1,)]
    with psycopg.connect(postgres_url) as conn:
        conn.execute("DELETE FROM documentos WHERE id = %s", (doc,))
    assert _filas(postgres_url, "SELECT count(*) FROM extracciones_linea") == [(0,)]


async def test_al_indexar_no_se_extrae_para_organizaciones_ni_prospectos_ni_si_se_apaga(
    client, org_a, cola, router, app, postgres_url, monkeypatch
):
    llm = _usar(app, LLMPorFragmento())
    expediente = await org_a.crear_expediente()
    doc = await _indexar(expediente, router, _lab(1, 91), "a.pdf")
    assert (await _extraer(client, org_a, expediente, doc)).json() == {"estado": "omitida"}

    with psycopg.connect(postgres_url) as conn:
        conn.execute("UPDATE tenants SET tipo = 'PERSONAL' WHERE id = %s", (org_a.tenant_id,))
        conn.execute("UPDATE documentos SET tipo_documento = 'PROSPECTO' WHERE id = %s", (doc,))
    assert (await _extraer(client, org_a, expediente, doc)).json() == {"estado": "omitida"}

    with psycopg.connect(postgres_url) as conn:
        conn.execute("UPDATE documentos SET tipo_documento = 'PLIEGO' WHERE id = %s", (doc,))
    monkeypatch.setattr(get_settings(), "cronologia_al_indexar", False)
    assert (await _extraer(client, org_a, expediente, doc)).json() == {"estado": "omitida"}
    assert llm.prompts == []


async def test_la_extraccion_interna_exige_el_token_y_respeta_el_tenant(
    client, personal, org_b, cola, router, app
):
    llm = _usar(app, LLMPorFragmento())
    expediente = await personal.crear_expediente()
    doc = await _indexar(expediente, router, _lab(1, 91), "a.pdf")
    assert (await _extraer(client, personal, expediente, doc, headers={})).status_code == 401
    assert (await _extraer(client, org_b, expediente, doc)).status_code == 404
    assert (await _extraer(client, personal, expediente, uuid.uuid4())).status_code == 404
    assert llm.prompts == []


async def test_si_el_modelo_falla_al_indexar_se_responde_503_y_no_se_guarda_nada(
    client, personal, cola, router, app, postgres_url
):
    _usar(app, LLMPorFragmento(fallar_si="Glucosa"))
    expediente = await personal.crear_expediente()
    doc = await _indexar(expediente, router, _lab(1, 91), "a.pdf")
    assert (await _extraer(client, personal, expediente, doc)).status_code == 503
    assert _filas(postgres_url, "SELECT count(*) FROM extracciones_linea") == [(0,)]
