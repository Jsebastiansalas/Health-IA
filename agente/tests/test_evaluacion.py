"""El evaluador de calidad: casos íntegros, métricas que distinguen un modelo bueno de uno malo."""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.core.db import get_sessionmaker
from app.ia.embeddings import EmbeddingRouter, get_router
from app.ia.llm import RespuestaLLM, get_llm
from app.pipeline.procesador import procesar_documento
from app.pipeline.vectorizacion import VectorizadorEmbeddings
from app.rag import seguridad
from evaluacion import casos, correr, metricas
from tests.fakes import EmbeddingsFalsos, subir
from tests.pdfs import pdf_texto

MODELO = "gemini-embedding-001"


# ---------- Integridad de los casos ----------
@pytest.mark.parametrize("caso", casos.RESPONDIBLES, ids=lambda c: c.pregunta)
def test_lo_esperado_esta_escrito_en_su_documento(caso):
    texto = metricas.normalizar(casos.DOCUMENTOS[caso.documento])
    assert metricas.normalizar(caso.fragmento) in texto
    assert any(metricas.normalizar(d) in texto for d in caso.datos)


@pytest.mark.parametrize("pregunta", casos.DE_LIMITE)
def test_toda_pregunta_de_limite_se_rechaza_sin_modelo(pregunta):
    assert seguridad.detectar_limite_clinico(pregunta)


@pytest.mark.parametrize("pregunta", [c.pregunta for c in casos.RESPONDIBLES] + casos.SIN_RESPUESTA)
def test_ninguna_pregunta_sobre_documentos_se_rechaza_por_error(pregunta):
    assert seguridad.detectar_limite_clinico(pregunta) is None


# ---------- Piezas de las métricas ----------
def _cuerpo(respuesta="", citas=(), sin_evidencia=False):
    return {
        "respuestaAnalitica": respuesta,
        "sinEvidencia": sin_evidencia,
        "citas": [{"documentoId": d, "extractoLiteral": e} for d, e in citas],
    }


def test_una_respuesta_vale_si_dice_el_dato_y_la_cita_correcta_lo_contiene():
    caso = casos.Pregunta("¿LDL?", "lab", "Colesterol LDL 160", ("160",))
    docs = {"lab": "id-lab", "otro": "id-otro"}
    bien = _cuerpo("Tu LDL fue 160 mg/dL.", [("id-lab", "Colesterol LDL 160 mg/dL")])
    assert metricas.puntuar_respuesta(caso, bien, docs) == (True, True)
    otro_doc = _cuerpo("Tu LDL fue 160.", [("id-otro", "Colesterol LDL 160 mg/dL")])
    assert metricas.puntuar_respuesta(caso, otro_doc, docs) == (True, False)
    sin_dato = _cuerpo("Está en tus documentos.", [("id-lab", "Colesterol")])
    assert metricas.puntuar_respuesta(caso, sin_dato, docs) == (False, False)
    abstenida = _cuerpo("160", [("id-lab", "160")], sin_evidencia=True)
    assert metricas.puntuar_respuesta(caso, abstenida, docs) == (False, False)


def test_las_cifras_de_la_respuesta_deben_estar_en_alguna_cita():
    bien = _cuerpo("LDL 160 y hemoglobina 13.2.", [("a", "LDL 160"), ("a", "Hemoglobina 13,2")])
    assert metricas.cifras_respaldadas(bien) == (2, 2)
    inventa = _cuerpo("LDL 160 y glucosa 300.", [("a", "LDL 160")])
    assert metricas.cifras_respaldadas(inventa) == (1, 2)


def test_comparar_avisa_de_lo_que_bajo_y_de_lo_que_dejo_de_medirse():
    base = {"recuperacion": 0.9, "limites": 1.0, "linea": 0.8}
    assert metricas.comparar({"recuperacion": 0.95, "limites": 1.0, "linea": 0.8}, base) == []
    avisos = metricas.comparar({"recuperacion": 0.5, "limites": 1.0}, base)
    assert len(avisos) == 2 and "recuperacion" in avisos[0] and "linea" in avisos[1]


def test_la_base_guardada_cubre_las_metricas_deterministas():
    base = json.loads((Path(correr.__file__).parent / "base.json").read_text(encoding="utf-8"))
    assert base["minimos"]["limites"] == 1.0
    assert base["minimos"]["anonimizacion_nombres"] >= 0.66
    assert set(base["minimos"]) == set(correr.METRICAS)


# ---------- Recorrido completo con modelos de mentira ----------
_FRAGMENTO = re.compile(r'<fragmento id="(F\d+)"[^>]*>\n(.*?)\n</fragmento>', re.DOTALL)


def _donde(fragmentos, aguja):
    for ident, texto in fragmentos:
        if metricas.normalizar(aguja) in metricas.normalizar(texto):
            return ident
    return None


class LLMOraculo:
    """Responde lo que se espera SOLO si el dato viene en el prompt: así una recuperación mala se nota."""

    modelo = "oraculo"

    async def generar_json(self, sistema, prompt, esquema):
        fr = _FRAGMENTO.findall(prompt)
        campos = esquema["properties"]
        if "hay_evidencia" in campos and "respuesta" in campos:
            pregunta = prompt.rsplit("PREGUNTA DEL USUARIO:\n", 1)[1].strip()
            caso = next((c for c in casos.RESPONDIBLES if c.pregunta == pregunta), None)
            ident = caso and _donde(fr, caso.fragmento)
            if not ident:
                datos = {
                    "respuesta": "No consta.",
                    "hay_evidencia": False,
                    "citas": [],
                    "alertas": [],
                }
            else:
                datos = {
                    "respuesta": f"El documento dice: {caso.datos[0]}.",
                    "hay_evidencia": True,
                    "citas": [{"fragmento": ident, "extracto_literal": caso.fragmento}],
                    "alertas": [],
                }
        elif "valores" in campos:
            valores = [
                {
                    "analito": v.analito,
                    "valor": v.valor,
                    "unidad": "",
                    "rango": "",
                    "marca": "",
                    "fecha_texto": v.fecha_texto,
                    "fragmento": i,
                    "extracto_literal": v.extracto,
                }
                for v in casos.VALORES
                if (i := _donde(fr, v.extracto))
            ]
            eventos = [
                {
                    "tipo": e.tipo,
                    "descripcion": e.extracto,
                    "fecha_texto": e.fecha_texto,
                    "fragmento": i,
                    "extracto_literal": e.extracto,
                }
                for e in casos.EVENTOS
                if (i := _donde(fr, e.extracto))
            ]
            datos = {"eventos": eventos, "valores": valores}
        elif "hallazgos" in campos:
            datos = {
                "hay_evidencia": True,
                "de_que_trata": "Un examen.",
                "hallazgos": [
                    {"texto": f"El documento dice {x}.", "fragmento": i, "extracto_literal": x}
                    for x in casos.EXPLICACION_ESPERADA
                    if (i := _donde(fr, x))
                ],
                "senales_de_alarma": [],
                "preguntas_para_el_medico": [],
            }
        else:
            datos = {"preguntas": []}
            for lista, clave in (
                ("medicamentos", "nombre"),
                ("diagnosticos", "texto"),
                ("alergias", "texto"),
            ):
                datos[lista] = [
                    {clave: x, "principio_activo": "", "fragmento": i, "extracto_literal": x}
                    for x in casos.PREPARACION_ESPERADA[lista]
                    if (i := _donde(fr, x))
                ]
        return RespuestaLLM(datos, self.modelo)


class LLMVacio:
    modelo = "vacio"

    async def generar_json(self, sistema, prompt, esquema):
        vacio = {k: [] for k, v in esquema["properties"].items() if v["type"] == "ARRAY"}
        if "hay_evidencia" in esquema["properties"]:
            vacio |= {"hay_evidencia": False, "respuesta": "", "de_que_trata": ""}
        return RespuestaLLM(vacio, self.modelo)


async def _correr(client, app, org, llm):
    router = EmbeddingRouter({MODELO: EmbeddingsFalsos(MODELO, 1536)})
    app.dependency_overrides[get_router] = lambda: router
    observador = correr.Observador(llm)
    app.dependency_overrides[get_llm] = lambda: observador
    expediente = await org.crear_expediente()
    documentos = {}
    with ThreadPoolExecutor(max_workers=1) as ex:
        for clave, texto in casos.DOCUMENTOS.items():
            r = await subir(
                expediente["id"], pdf_texto([texto]), tipo="HISTORIA_CLINICA", nombre=f"{clave}.pdf"
            )
            documentos[clave] = r.json()["id"]
            await procesar_documento(
                get_sessionmaker(), documentos[clave], ex, VectorizadorEmbeddings(router)
            )
    ids = correr.Ids(str(org.tenant_id), expediente["id"], str(org.admin_id), documentos)
    return await correr.evaluar(client, ids, observador, {"X-Internal-Token": correr.token()})


async def test_un_modelo_perfecto_saca_la_nota_maxima(client, app, org_a):
    informe = await _correr(client, app, org_a, LLMOraculo())
    medidas = informe["medidas"]
    assert set(medidas) == set(correr.METRICAS)
    malas = {k: v for k, v in medidas.items() if v < 1.0 and not k.startswith("anonimizacion")}
    assert not malas, (malas, informe["fallos"])


async def test_un_modelo_que_no_responde_hace_fallar_la_comparacion(client, app, org_a):
    informe = await _correr(client, app, org_a, LLMVacio())
    medidas = informe["medidas"]
    assert medidas["respuesta"] == 0 and medidas["linea_encontrados"] == 0
    assert medidas["explicacion"] == 0 and medidas["preparacion"] == 0
    assert medidas["abstencion"] == 1 and medidas["limites"] == 1
    base = {k: 0.5 for k in correr.METRICAS}
    assert any("respuesta" in a for a in metricas.comparar(medidas, base))
    assert informe["fallos"]


def test_sin_credenciales_no_arranca_nada_y_sale_con_2(monkeypatch, capsys):
    monkeypatch.setattr(correr, "credenciales", lambda: False)
    assert correr.main([]) == 2
    assert "credenciales" in capsys.readouterr().out.lower()
