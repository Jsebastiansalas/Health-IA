"""Fichas técnicas (CIMA): carga con fuente, nunca posología, y respuestas clínicas solo con ficha citada."""

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.db import get_sessionmaker
from app.medicamentos import consulta, fichas
from tests.conftest import interno
from tests.test_medicamentos import LLMFalso, con_llm, cuerpo, sembrar

HTML_CONTRA = (
    '<div><p style="margin:0">Este medicamento est&#225; contraindicado:</p>'
    "<ul><li><span>en pacientes con &#250;lcera g&#225;strica</span></li>"
    "<li>embarazo (tercer trimestre)</li></ul></div>"
)
HTML_INTERACCION = "<div><p>Puede aumentar el efecto de los anticoagulantes.</p></div>"


@pytest.fixture(autouse=True)
def _cima_activo(monkeypatch):
    """Estos casos prueban las fichas de CIMA: se activan (en producción están apagadas por defecto)."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "fichas_cima_activas", True)


def cima_falsa(pedidas: list[str]) -> httpx.AsyncClient:
    def manejar(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/medicamentos"):
            return httpx.Response(
                200,
                json={
                    "resultados": [
                        {
                            "nregistro": "111",
                            "nombre": "IBUPROFENO FALSO 400 MG",
                            "docs": [{"tipo": 1, "secc": True}],
                        },
                        {
                            "nregistro": "222",
                            "nombre": "SIN FICHA",
                            "docs": [{"tipo": 2, "secc": True}],
                        },
                    ]
                },
            )
        seccion = req.url.params["seccion"]
        pedidas.append(seccion)
        contenido = {"4.3": HTML_CONTRA, "4.5": HTML_INTERACCION}.get(seccion)
        if contenido is None:
            return httpx.Response(200, json={"error": "No existen secciones"})
        return httpx.Response(
            200, json=[{"seccion": seccion, "titulo": "x", "contenido": contenido}]
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(manejar))


async def cargar_ibuprofeno() -> list[str]:
    pedidas: list[str] = []
    async with cima_falsa(pedidas) as c, get_sessionmaker()() as s:
        await fichas.cargar_fichas(s, c, ["Ibuprofeno"])
    return pedidas


def test_el_html_de_una_seccion_queda_como_texto_legible():
    t = fichas.html_a_texto(HTML_CONTRA)
    assert "contraindicado:" in t and "- en pacientes con úlcera gástrica" in t and "<" not in t
    assert "- embarazo (tercer trimestre)" in t


def test_nunca_se_cargan_posologia_ni_sobredosis():
    assert "4.2" not in fichas.SECCIONES and "4.9" not in fichas.SECCIONES
    assert set(fichas.SECCIONES) == {"4.1", "4.3", "4.4", "4.5", "4.6", "4.8"}


async def test_la_carga_guarda_secciones_con_enlace_y_sin_posologia(client: AsyncClient):
    pedidas = await cargar_ibuprofeno()
    assert "4.2" not in pedidas and "4.9" not in pedidas
    async with get_sessionmaker()() as s:
        filas = (await s.execute(text("select * from med_ficha order by seccion"))).mappings().all()
    assert [f["seccion"] for f in filas] == [
        "4.3",
        "4.5",
    ]  # solo las que existen; la 222 no tiene ficha
    assert all(f["nregistro"] == "111" and f["principio_norm"] == "ibuprofeno" for f in filas)
    assert (
        filas[0]["url_origen"].endswith("/ft/111/FT_111.html")
        and "úlcera gástrica" in filas[0]["texto"]
    )


async def test_recargar_reemplaza_en_lugar_de_duplicar(client: AsyncClient):
    await cargar_ibuprofeno()
    await cargar_ibuprofeno()
    async with get_sessionmaker()() as s:
        assert (await s.scalar(text("select count(*) from med_ficha"))) == 2


async def test_fichas_de_busca_por_principio_sin_tildes_ni_mayusculas(client: AsyncClient):
    await cargar_ibuprofeno()
    async with get_sessionmaker()() as s:
        assert len(await fichas.fichas_de(s, "IBUPROFENO")) == 2
        assert len(await fichas.fichas_de(s, "ibuprofen")) == 2  # coincidencia parcial
        assert await fichas.fichas_de(s, "paracetamol") == []
        assert await fichas.fichas_de(s, "") == []


def redaccion(**extra) -> dict:
    return {
        "respuesta": "La ficha dice que está contraindicado en úlcera gástrica [F1].",
        "hay_evidencia": True,
        "registros_usados": [],
        "precios_usados": [],
        "usa_estadisticas": False,
        "fichas_usadas": ["F1"],
    } | extra


async def test_una_pregunta_clinica_se_responde_solo_con_la_ficha_citada(client: AsyncClient, app):
    await sembrar()
    await cargar_ibuprofeno()
    llm = LLMFalso(
        {"tipo": "clinica", "principio_activo": "ibuprofeno"},
        redaccion(fichas_usadas=["F1", "F99"]),
    )
    con_llm(app, llm)
    r = await client.post(
        "/internal/v1/medicamentos/consultas",
        json=cuerpo("¿Quién no debe tomar ibuprofeno?"),
        headers=interno(),
    )
    assert r.status_code == 200, r.text
    j = r.json()
    citas = [c for c in j["citas"] if c["tipo"] == "FICHA_TECNICA"]
    assert len(citas) == 1 and j["sinEvidencia"] is False  # F99 no existe: no genera cita
    c = citas[0]
    assert c["seccion"] == "4.3" and "úlcera gástrica" in c["extractoLiteral"]
    assert c["fuente"]["enlace"].endswith("FT_111.html") and "AEMPS" in c["fuente"]["licencia"]
    assert any("España" in a for a in j["alertas"])
    # el modelo recibió la ficha y las reglas que le prohíben dosificar o elegir por la persona
    assert '<ficha id="F1">' in llm.prompts[1]
    assert "NUNCA indiques dosis" in consulta.SISTEMA_REDACTOR
    assert "qué medicamento debe tomar" in consulta.SISTEMA_REDACTOR


async def test_sin_fichas_cargadas_la_respuesta_clinica_no_cita_nada_inventado(
    client: AsyncClient, app
):
    await sembrar()
    llm = LLMFalso(
        {"tipo": "clinica", "principio_activo": "acetaminofen"},
        redaccion(
            respuesta="Esos datos no están en la fuente.", hay_evidencia=False, fichas_usadas=["F1"]
        ),
    )
    con_llm(app, llm)
    r = await client.post(
        "/internal/v1/medicamentos/consultas",
        json=cuerpo("¿Qué efectos adversos tiene el acetaminofén?"),
        headers=interno(),
    )
    j = r.json()
    assert not [c for c in j["citas"] if c["tipo"] == "FICHA_TECNICA"]
    assert j["sinEvidencia"] is True
    assert "<ficha" not in llm.prompts[1]


def test_el_aviso_no_promete_dosis_ni_dice_que_tomar():
    assert "no indica dosis" in consulta.AVISO and "123" in consulta.AVISO
