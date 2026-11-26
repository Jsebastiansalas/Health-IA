"""Base de medicamentos de INVIMA: normalización, carga paginada, búsqueda y consulta con citas."""

from datetime import date

import httpx
import pytest
from httpx import AsyncClient

from app.core.db import get_sessionmaker
from app.ia.llm import RespuestaLLM, get_llm
from app.medicamentos import busqueda, consulta
from app.medicamentos.busqueda import Filtros
from app.medicamentos.carga import Agrupador, cargar_fuente, fila_cum, fila_precio
from app.medicamentos.normalizar import fecha, normalizar, numero
from tests.conftest import interno


# ---------- Datos de ejemplo con la forma real del conjunto de INVIMA ----------
def fila(exp, cons, producto, principio, cantidad="50", unidad="mg", **extra) -> dict:
    base = {
        "expediente": exp,
        "expedientecum": exp,
        "consecutivocum": cons,
        "producto": producto,
        "titular": "LABORATORIOS EJEMPLO S.A.",
        "registrosanitario": f"INVIMA 2023M-{int(exp):07d}-R1",
        "fechaexpedicion": "08/23/2012",
        "fechavencimiento": "08/23/2032",
        "estadoregistro": "Vigente",
        "estadocum": "Activo",
        "descripcioncomercial": "CAJA POR 30 TABLETAS EN BLISTER",
        "atc": "C09CA01",
        "descripcionatc": "LOSARTAN",
        "viaadministracion": "ORAL",
        "principioactivo": principio,
        "unidadmedida": unidad,
        "cantidad": cantidad,
        "unidadreferencia": "TABLETA RECUBIERTA",
        "formafarmaceutica": "TABLETA RECUBIERTA",
        "nombrerol": "LABORATORIOS EJEMPLO S.A.",
        "tiporol": "TITULAR",
        "modalidad": "FABRICAR Y VENDER",
    }
    return {**base, **extra}


FILAS_VIGENTES = [
    fila("1001", "1", "COZAAR", "LOSARTAN POTASICO", "50", titular="MERCK SHARP & DOHME"),
    fila("1001", "2", "COZAAR", "LOSARTAN POTASICO", "100", titular="MERCK SHARP & DOHME"),
    # combinación: dos filas del mismo CUM (una por principio activo)
    fila("1002", "1", "LOSARTAN HCT", "LOSARTAN POTASICO", "50", titular="LABORATORIOS GENFAR"),
    fila("1002", "1", "LOSARTAN HCT", "HIDROCLOROTIAZIDA", "12.5", titular="LABORATORIOS GENFAR"),
    fila(
        "1003",
        "1",
        "ACETAMINOFÉN MK",
        "ACETAMINOFEN",
        "500",
        atc="N02BE01",
        descripcionatc="PARACETAMOL",
        titular="TECNOQUIMICAS S.A.",
        fechavencimiento="01/05/2020",  # vencida según fecha aunque figure vigente
    ),
]

PRECIOS = [
    {
        "cum": "1003-1",
        "medicamento": "ACETAMINOFEN 500 mg tableta",
        "mercado_relevante": "Acetaminofen - Solido - oral",
        "precio_maximo_de_venta_transaccion_primaria_secundaria_y_final_institucional": "120.5",
        "precio_maximo_de_venta_transaccion_final_comercial": "150",
        "circular_cnpmdm": "Circular 06 de 2013",
        "fecha_de_inicio_vigencia_precio_maximo_de_venta": "2013-10-03T00:00:00.000",
    }
]


def cliente_falso(datos_por_dataset: dict[str, list[dict]]) -> httpx.AsyncClient:
    """Sirve cada dataset por páginas, respetando $limit/$offset como la API Socrata."""

    def manejar(req: httpx.Request) -> httpx.Response:
        dataset = req.url.path.rsplit("/", 1)[-1].removesuffix(".json")
        filas = datos_por_dataset.get(dataset, [])
        limite = int(req.url.params["$limit"])
        desde = int(req.url.params["$offset"])
        return httpx.Response(200, json=filas[desde : desde + limite])

    return httpx.AsyncClient(transport=httpx.MockTransport(manejar))


async def sembrar() -> None:
    import app.medicamentos.carga as carga

    carga.PAGINA = 3  # fuerza varias páginas
    datos = {"i7cb-raxc": FILAS_VIGENTES, "nauz-qkjw": PRECIOS}
    async with cliente_falso(datos) as c:
        for fuente in ("VIGENTE", "PRECIO"):
            async with get_sessionmaker()() as s:
                await cargar_fuente(s, c, fuente)


@pytest.fixture(autouse=True)
def _pagina_original():
    import app.medicamentos.carga as carga

    original = carga.PAGINA
    yield
    carga.PAGINA = original


# ---------- Unitarias ----------
def test_normalizar_quita_tildes_y_signos():
    assert normalizar("ACETAMINOFÉN 500 mg/5 mL") == "acetaminofen 500 mg 5 ml"
    assert normalizar(None) == ""


def test_fecha_y_numero():
    assert fecha("08/23/2012") == date(2012, 8, 23)
    assert fecha("2013-10-03T00:00:00.000") == date(2013, 10, 3)
    assert fecha("") is None and fecha("basura") is None
    assert str(numero("12,5")) == "12.5" and numero("x") is None


def test_agrupador_une_principios_de_un_mismo_cum_entre_paginas():
    a = Agrupador()
    listos = a.alimentar(FILAS_VIGENTES[:3])  # la fila 3 deja abierto el CUM 1002-1
    assert [g.base["expedientecum"] for g in listos] == ["1001", "1001"]
    listos += a.alimentar(FILAS_VIGENTES[3:])
    listos += a.cerrar()
    cums = {(g.base["expedientecum"], g.base["consecutivocum"]): g for g in listos}
    combinado = cums[("1002", "1")]
    assert [p["nombre"] for p in combinado.principios] == ["LOSARTAN POTASICO", "HIDROCLOROTIAZIDA"]
    assert len(cums) == 4


def test_fila_cum_y_precio():
    g = Agrupador()
    g.alimentar([FILAS_VIGENTES[0]])
    f = fila_cum("VIGENTE", g.cerrar()[0])
    assert f["producto_n"] == "cozaar" and "merck" in f["titular_n"]
    assert "losartan potasico" in f["busqueda"] and "1001 1" in f["busqueda"]
    p = fila_precio(PRECIOS[0])
    assert p["precio_institucional"] is not None and p["vigencia_desde"] == date(2013, 10, 3)


# ---------- Carga y búsqueda contra PostgreSQL real ----------
async def test_la_carga_agrupa_y_registra_la_procedencia(client: AsyncClient):
    await sembrar()
    async with get_sessionmaker()() as s:
        fuentes = {f["fuente"]: f for f in await busqueda.fuentes_cargadas(s)}
        assert fuentes["VIGENTE"]["filas"] == 4 and fuentes["VIGENTE"]["dataset_id"] == "i7cb-raxc"
        assert fuentes["PRECIO"]["filas"] == 1


async def test_recargar_reemplaza_en_lugar_de_duplicar(client: AsyncClient):
    await sembrar()
    await sembrar()
    async with get_sessionmaker()() as s:
        r = await busqueda.buscar(s, Filtros(principio_activo="losartan"), 20)
        assert r.total_cum == 3


async def test_busca_por_principio_activo_y_concentracion(client: AsyncClient):
    await sembrar()
    async with get_sessionmaker()() as s:
        r = await busqueda.buscar(s, Filtros(principio_activo="losartán", concentracion="100 mg"))
        assert [x["producto"] for x in r.registros] == ["COZAAR"]
        r = await busqueda.buscar(s, Filtros(principio_activo="hidroclorotiazida"))
        assert [x["producto"] for x in r.registros] == ["LOSARTAN HCT"]
        # la marca no se confunde con el principio activo
        r = await busqueda.buscar(s, Filtros(principio_activo="cozaar"))
        assert not r.registros or r.aproximada


async def test_agrupa_presentaciones_por_registro_y_cuenta_titulares(client: AsyncClient):
    await sembrar()
    async with get_sessionmaker()() as s:
        r = await busqueda.buscar(s, Filtros(principio_activo="losartan"))
    assert r.total_cum == 3 and r.total_registros == 2
    cozaar = next(x for x in r.registros if x["producto"] == "COZAAR")
    assert cozaar["presentaciones"] == 2
    assert r.titulares_distintos == 2


async def test_busca_por_titular_cum_y_registro(client: AsyncClient):
    await sembrar()
    async with get_sessionmaker()() as s:
        assert (await busqueda.buscar(s, Filtros(titular="tecnoquimicas"))).total_cum == 1
        assert (await busqueda.buscar(s, Filtros(cum="1001-2"))).registros[0]["consecutivo"] == "2"
        assert (
            await busqueda.buscar(s, Filtros(registro_sanitario="2023M-0001003"))
        ).total_cum == 1
        assert (await busqueda.buscar(s, Filtros(atc="C09"))).total_cum == 3
        assert (
            await busqueda.buscar(s, Filtros(principio_activo="losartan", estado="VENCIDO"))
        ).total_cum == 0


async def test_error_de_escritura_se_resuelve_por_similitud_y_se_marca(client: AsyncClient):
    await sembrar()
    async with get_sessionmaker()() as s:
        r = await busqueda.buscar(s, Filtros(producto="acetaminofen mk"))
        assert r.total_cum == 1 and not r.aproximada
        r = await busqueda.buscar(s, Filtros(principio_activo="acetaminofn"))
        assert r.total_cum == 1 and r.aproximada


async def test_precios_por_cum_y_por_nombre(client: AsyncClient):
    await sembrar()
    async with get_sessionmaker()() as s:
        r = await busqueda.buscar(s, Filtros(principio_activo="acetaminofen"))
        por_cum = await busqueda.buscar_precios(
            s, Filtros(principio_activo="acetaminofen"), r.registros
        )
        assert por_cum and por_cum[0]["cum"] == "1003-1"
        por_nombre = await busqueda.buscar_precios(s, Filtros(principio_activo="acetaminofen"), [])
        assert por_nombre


# ---------- Consulta completa con un modelo falso ----------
class LLMFalso:
    """Primera llamada: interpreta. Segunda: redacta usando el primer registro."""

    def __init__(self, interpretacion: dict, redaccion: dict | None = None):
        self.interpretacion = interpretacion
        self.redaccion = redaccion
        self.prompts: list[str] = []

    async def generar_json(self, sistema: str, prompt: str, esquema: dict) -> RespuestaLLM:
        self.prompts.append(prompt)
        if "filtros de búsqueda" in sistema:
            return RespuestaLLM(self.interpretacion, "falso")
        assert self.redaccion is not None, "no debió llamarse al redactor"
        return RespuestaLLM(self.redaccion, "falso")


def con_llm(app, llm) -> None:
    app.dependency_overrides[get_llm] = lambda: llm


def cuerpo(pregunta: str) -> dict:
    return {
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "usuario_id": "00000000-0000-0000-0000-000000000002",
        "pregunta": pregunta,
    }


async def test_consulta_con_citas_construidas_desde_la_base(client: AsyncClient, app):
    await sembrar()
    llm = LLMFalso(
        {"tipo": "ficha", "principio_activo": "acetaminofen", "estado": ""},
        {
            "respuesta": "El acetaminofén MK tiene registro INVIMA 2023M-0001003-R1 [R1].",
            "hay_evidencia": True,
            "registros_usados": ["R1", "R99"],  # R99 no existe: se descarta
            "precios_usados": ["P1"],
            "usa_estadisticas": False,
        },
    )
    con_llm(app, llm)
    r = await client.post(
        "/internal/v1/medicamentos/consultas",
        json=cuerpo("¿Qué registro tiene el acetaminofén MK?"),
        headers=interno(),
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["sinEvidencia"] is False
    registros = [c for c in j["citas"] if c["tipo"] == "REGISTRO_INVIMA"]
    assert len(registros) == 1  # el id inexistente no genera cita
    c = registros[0]
    assert c["registroSanitario"] == "INVIMA 2023M-0001003-R1" and c["cum"] == "1003-1"
    assert c["fuente"]["datasetId"] == "i7cb-raxc" and "expedientecum=1003" in c["fuente"]["enlace"]
    assert "CC BY-SA" in c["fuente"]["licencia"]
    assert any(x["tipo"] == "PRECIO_REGULADO" and x["precioInstitucional"] for x in j["citas"])
    # figura vigente pero su fecha de vencimiento ya pasó: lo detecta el código, no el modelo
    assert any("ya pasó" in a for a in j["alertas"])
    assert "no reemplaza" in j["aviso"].lower()
    assert "R1" in llm.prompts[1] and "FECHA DE HOY" in llm.prompts[1]


async def test_estadisticas_se_citan_como_consulta_agregada(client: AsyncClient, app):
    await sembrar()
    con_llm(
        app,
        LLMFalso(
            {"tipo": "conteo", "principio_activo": "losartan", "estado": "VIGENTE"},
            {
                "respuesta": "Hay 2 registros con losartán.",
                "hay_evidencia": True,
                "registros_usados": [],
                "precios_usados": [],
                "usa_estadisticas": True,
            },
        ),
    )
    j = (
        await client.post(
            "/internal/v1/medicamentos/consultas",
            json=cuerpo("¿Cuántos registros de losartán hay?"),
            headers=interno(),
        )
    ).json()
    agregada = next(c for c in j["citas"] if c["tipo"] == "CONSULTA_AGREGADA")
    assert agregada["registrosSanitarios"] == 2 and agregada["titularesDistintos"] == 2
    assert agregada["filtros"]["principio_activo"] == "losartan"


async def test_sin_coincidencias_no_gasta_la_segunda_llamada(client: AsyncClient, app):
    await sembrar()
    llm = LLMFalso({"tipo": "ficha", "producto": "medicamento inexistente xyz"})
    con_llm(app, llm)
    j = (
        await client.post(
            "/internal/v1/medicamentos/consultas", json=cuerpo("¿Qué es xyz?"), headers=interno()
        )
    ).json()
    assert j["sinEvidencia"] is True and j["citas"] == []
    assert len(llm.prompts) == 1


async def test_pregunta_fuera_de_alcance_y_sin_filtros(client: AsyncClient, app):
    await sembrar()
    con_llm(app, LLMFalso({"tipo": "fuera_de_alcance"}))
    j = (
        await client.post(
            "/internal/v1/medicamentos/consultas",
            json=cuerpo("¿Cómo está el clima?"),
            headers=interno(),
        )
    ).json()
    assert j["sinEvidencia"] is True and "medicamentos" in j["respuestaAnalitica"]
    con_llm(app, LLMFalso({"tipo": "listado"}))
    j = (
        await client.post(
            "/internal/v1/medicamentos/consultas", json=cuerpo("¿Qué hay?"), headers=interno()
        )
    ).json()
    assert j["sinEvidencia"] is True and "Indica un medicamento" in j["respuestaAnalitica"]


async def test_sin_base_cargada_lo_dice(client: AsyncClient, app):
    con_llm(app, LLMFalso({"tipo": "ficha", "producto": "x"}))
    j = (
        await client.post(
            "/internal/v1/medicamentos/consultas", json=cuerpo("¿Qué es x?"), headers=interno()
        )
    ).json()
    assert j["sinEvidencia"] is True and "no está cargada" in j["respuestaAnalitica"]


async def test_endpoint_exige_token_y_lista_fuentes(client: AsyncClient):
    assert (
        await client.post("/internal/v1/medicamentos/consultas", json=cuerpo("hola mundo"))
    ).status_code == 401
    assert (await client.get("/internal/v1/medicamentos/fuentes")).status_code == 401
    await sembrar()
    r = await client.get("/internal/v1/medicamentos/fuentes", headers=interno())
    assert {f["fuente"] for f in r.json()} == {"VIGENTE", "PRECIO"}


def test_el_prompt_del_interprete_se_reconoce():
    # El doble de prueba distingue las dos llamadas por esta frase del sistema.
    assert "filtros de búsqueda" in consulta.SISTEMA_INTERPRETE


def _valores_de_enum(esquema) -> list[list]:
    """Todas las listas `enum` anidadas en un esquema."""
    if isinstance(esquema, dict):
        encontrados = [esquema["enum"]] if "enum" in esquema else []
        for v in esquema.values():
            encontrados += _valores_de_enum(v)
        return encontrados
    if isinstance(esquema, list):
        return [e for v in esquema for e in _valores_de_enum(v)]
    return []


def test_los_esquemas_no_llevan_enums_vacios_que_gemini_rechaza():
    # Gemini responde 400 si algún valor de un enum es la cadena vacía.
    for esquema in (consulta.ESQUEMA_INTERPRETE, consulta.ESQUEMA_REDACTOR):
        for valores in _valores_de_enum(esquema):
            assert valores and all(v != "" for v in valores)


def test_cualquiera_equivale_a_sin_estado():
    tipo, f = consulta._a_filtros({"tipo": "ficha", "estado": "CUALQUIERA", "producto": "x"})
    assert f.estado == "" and tipo == "ficha"


async def test_si_no_hay_precio_regulado_se_le_dice_al_redactor(client: AsyncClient, app):
    await sembrar()
    llm = LLMFalso(
        {"tipo": "precio", "principio_activo": "losartan"},
        {
            "respuesta": "No hay precio regulado para estas presentaciones.",
            "hay_evidencia": True,
            "registros_usados": ["R1"],
            "precios_usados": [],
            "usa_estadisticas": False,
        },
    )
    con_llm(app, llm)
    j = (
        await client.post(
            "/internal/v1/medicamentos/consultas",
            json=cuerpo("Precio del losartán"),
            headers=interno(),
        )
    ).json()
    assert "NO hay precio regulado" in llm.prompts[1]
    assert j["sinEvidencia"] is False and all(c["tipo"] != "PRECIO_REGULADO" for c in j["citas"])
