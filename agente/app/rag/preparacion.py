# ruff: noqa: E501
"""«Preparar mi cita»: un resumen de una página para llevar al médico, con cita en cada dato.

Junta, sin interpretar:
- lo más reciente de la línea de tiempo (sprint 37, reutilizada si los documentos no cambiaron);
- los exámenes que cambiaron entre dos fechas (primer y último valor, tal como están escritos);
- los medicamentos, diagnósticos y alergias que escriben los documentos (la misma extracción validada
  del cruce de medicamentos);
- preguntas sugeridas para el médico. Son solo preguntas: se descarta cualquiera que afirme, recete,
  dosifique o traiga cifras que los documentos no contengan. La persona las edita antes de descargar.

El PDF se arma en el navegador de la persona: el servidor no guarda ni genera el archivo.
"""

import copy
import re
import time
import uuid

from app.core.config import Settings
from app.core.db import fijar_tenant, get_sessionmaker
from app.ia.llm import ProveedorLLM
from app.models import Expediente
from app.privacidad.anonimizar import Anonimizador, evidencias_para_la_nube
from app.rag import cronologia, cruce, garantias, generacion
from app.rag.busqueda import _fila
from app.rag.motor import cita_a_json

PREGUNTA_HISTORIAL = "[Preparar mi cita]"
MAX_EVENTOS = 8
MAX_PREGUNTAS = 6

AVISO_GENERAL = (
    "Este resumen junta lo que dicen tus documentos para que lo lleves a tu cita. No es un diagnóstico "
    "ni reemplaza la conversación con tu médico. Las preguntas son sugerencias: cámbialas o agrega las "
    "tuyas. Si es una urgencia, llama al 123."
)
MENSAJE_SIN_DATOS = (
    "Todavía no hay documentos leídos en este expediente. Sube tus resultados, fórmulas u órdenes y "
    "vuelve a preparar tu cita."
)

SISTEMA = (
    cruce.SISTEMA_EXTRAER
    + """
Además, propón entre 3 y 6 PREGUNTAS que la persona podría llevarle a su médico sobre lo que dicen estos
documentos (por ejemplo, sobre un resultado que el documento marca, un control indicado o un medicamento
que aparece). Reglas para las preguntas:
- Cada una es una sola pregunta dirigida al médico, termina en «?» y tiene máximo 160 caracteres.
- No contestes las preguntas, no sugieras diagnósticos ni tratamientos y no escribas dosis.
- No escribas cifras que no estén en los fragmentos."""
)

ESQUEMA = copy.deepcopy(cruce.ESQUEMA_EXTRAER)
ESQUEMA["properties"]["preguntas"] = {"type": "ARRAY", "items": {"type": "STRING"}}
ESQUEMA["required"] = [*ESQUEMA["required"], "preguntas"]

_AFIRMA_DIAGNOSTICO = re.compile(
    r"\b(?:tienes|padeces|sufres|es (?:un|una) (?:sintoma|signo)|significa que (?:tienes|padeces))\b"
)


def validar_preguntas(propuestas: list, fuentes: list[str]) -> list[str]:
    """Solo quedan preguntas de verdad: terminan en «?», no afirman cifras ni juicios que los documentos no
    dicen, no traen una posología sin respaldo ni afirman un diagnóstico. Sin repetidas y máximo seis."""
    respaldo = "\n".join(fuentes)
    salida: list[str] = []
    vistas: set[str] = set()
    for p in propuestas or []:
        q = " ".join(str(p or "").split())
        # «El LDL estaba alto, ¿cómo ha evolucionado?» ya trae su «¿»: solo se agrega si no hay ninguno.
        if "¿" not in q:
            q = "¿" + q
        n = cronologia._norm(q)
        if (
            not q.endswith("?")
            or len(q) > 200
            or len(q) < 12
            or n in vistas
            or garantias.afirma_sin_respaldo(q, respaldo)
            or garantias.posologia_sin_respaldo(q, fuentes)
            or _AFIRMA_DIAGNOSTICO.search(n)
        ):
            continue
        vistas.add(n)
        salida.append(q)
        if len(salida) == MAX_PREGUNTAS:
            break
    return salida


def cambios_de(linea: dict) -> list[dict]:
    """Exámenes con al menos dos mediciones fechadas: el primero y el último valor, tal como están escritos."""
    salida = []
    for a in linea.get("analitos") or []:
        fechados = [v for v in a.get("valores") or [] if v.get("fecha")]
        if not a.get("comparable") or len(fechados) < 2:
            continue
        desde, hasta = fechados[0], fechados[-1]
        salida.append(
            {
                "nombre": a["nombre"],
                "mediciones": len(fechados),
                "desde": {
                    k: desde.get(k) for k in ("fecha", "valorTexto", "unidad", "marca", "cita")
                },
                "hasta": {
                    k: hasta.get(k) for k in ("fecha", "valorTexto", "unidad", "marca", "cita")
                },
            }
        )
    return salida


def recientes(linea: dict) -> list[dict]:
    """Los últimos eventos de la línea de tiempo (ya vienen ordenados por fecha)."""
    con_fecha = [e for e in linea.get("eventos") or [] if e.get("fecha") or e.get("referencia")]
    return con_fecha[-MAX_EVENTOS:][::-1]


async def preparar(expediente: Expediente, llm: ProveedorLLM, s: Settings, linea: dict) -> dict:
    t0 = time.perf_counter()
    async with get_sessionmaker()() as session:
        fijar_tenant(session, expediente.tenant_id)
        filas = await session.execute(
            cronologia.SQL_FRAGMENTOS,
            {
                "tenant_id": expediente.tenant_id,
                "expediente_id": expediente.id,
                "modelo": expediente.embedding_model_activo,
                "limite": s.cronologia_max_fragmentos,
            },
        )
        evidencias = [_fila(r) for r in filas]

    consulta_id = uuid.uuid4()
    citas_linea: list[dict] = list(linea.get("citas") or [])
    cuerpo: dict = {
        "consultaId": str(consulta_id),
        "modo": "preparacion",
        "respuestaAnalitica": "Resumen para tu próxima cita.",
        "avisoGeneral": AVISO_GENERAL,
        "eventos": recientes(linea),
        "cambios": cambios_de(linea),
        "medicamentos": [],
        "diagnosticos": [],
        "alergias": [],
        "preguntas": [],
        "alertas": [],
        "citas": citas_linea,
        "sinEvidencia": False,
        "modeloEmbeddings": expediente.embedding_model_activo,
        "modeloLlm": None,
        "fragmentosRecuperados": len(evidencias),
        "latenciaMs": 0,
    }
    if not evidencias:
        cuerpo.update(
            respuestaAnalitica=MENSAJE_SIN_DATOS, sinEvidencia=True, eventos=[], cambios=[]
        )
        return cuerpo

    anon = Anonimizador() if s.anonimizar_antes_de_nube else None
    nube = evidencias_para_la_nube(evidencias, anon) if anon else evidencias
    salida = await llm.generar_json(
        SISTEMA,
        generacion.construir_prompt(
            "Extrae medicamentos, diagnósticos y alergias, y propón preguntas para el médico.", nube
        ),
        ESQUEMA,
    )
    datos = anon.restaurar_json(salida.datos) if anon else salida.datos
    citas, meds, diags, alergias = cruce.extraer_elementos(
        datos, evidencias, s.umbral_confianza_ocr
    )
    # Las citas de esta extracción van después de las de la línea de tiempo.
    desplazar = len(citas_linea)
    for lista in (meds, diags, alergias):
        for x in lista:
            x["cita"] += desplazar
    fuentes = [e.contenido_texto for e in evidencias]
    preguntas = validar_preguntas(datos.get("preguntas") or [], fuentes)
    descartadas = len(datos.get("preguntas") or []) - len(preguntas)
    cuerpo.update(
        medicamentos=[{"nombre": m["nombre"], "cita": m["cita"]} for m in meds],
        diagnosticos=diags,
        alergias=alergias,
        preguntas=preguntas,
        citas=citas_linea + [cita_a_json(c) for c in citas.lista],
        modeloLlm=salida.modelo,
    )
    if descartadas > 0:
        cuerpo["alertas"].append(
            f"Se descartaron {descartadas} pregunta(s) sugerida(s) que afirmaban algo que tus documentos no dicen."
        )
    if not (cuerpo["eventos"] or cuerpo["cambios"] or meds or diags or alergias):
        cuerpo.update(respuestaAnalitica=MENSAJE_SIN_DATOS, sinEvidencia=True)
    cuerpo["latenciaMs"] = int((time.perf_counter() - t0) * 1000)
    return cuerpo
