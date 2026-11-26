# ruff: noqa: E501
"""Línea de tiempo del expediente y evolución de resultados de laboratorio, con cita en cada dato.

Ordena por fecha lo que dicen los documentos (consultas, exámenes, hospitalizaciones, procedimientos,
fórmulas y controles indicados) y agrupa los valores de un mismo examen que aparecen en varias fechas.
NUNCA interpreta: no dice si un valor es bueno, malo, normal o preocupante; muestra el valor, la unidad,
el rango y la marca (ALTO/BAJO) solo si el documento los trae impresos.

El modelo solo propone; todo se comprueba aquí contra el texto literal:
- cada elemento cita un fragmento real y su extracto se localiza en él;
- el número, la unidad, el rango, la marca y el nombre del examen deben estar escritos en ese fragmento;
- la fecha debe estar escrita en algún fragmento del mismo documento, y la convierte a fecha este
  código (no el modelo). Una fecha que no se entiende sin ambigüedad se muestra como está escrita y
  no se ubica en la línea;
- una descripción con cifras, juicios o dosis que el fragmento no respalda se descarta.

El modelo lee cada documento una sola vez (`app.rag.extraccion_linea`); armar la línea con lo ya
leído no lo llama.
"""

import hashlib
import re
import time
import unicodedata
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.ia.llm import ProveedorLLM
from app.models import Expediente
from app.rag import extraccion_linea, garantias
from app.rag.busqueda import _FILTRO_SEGURO, FragmentoRecuperado, _fila
from app.rag.cruce import _Citas, _t

PREGUNTA_HISTORIAL = "[Línea de tiempo]"
# Un control que el documento indica sin fecha ni plazo («control con cardiología»).
SIN_FECHA_ESCRITA = "sin fecha escrita"

AVISO_GENERAL = (
    "Esta línea de tiempo ordena lo que dicen tus documentos, con su cita. No interpreta tus resultados: "
    "los rangos y las marcas (ALTO, BAJO) son los que trae impresos cada documento, y pueden cambiar de "
    "un laboratorio a otro. Lo que significan para ti lo explica tu médico. Si es una urgencia, llama al 123."
)
MENSAJE_SIN_DATOS = (
    "No encontré fechas, consultas ni resultados con fecha en los documentos de este expediente. Sube "
    "resultados de laboratorio, epicrisis, órdenes o fórmulas y vuelve a intentarlo."
)

TIPOS_EVENTO = {
    "CONSULTA",
    "EXAMEN",
    "HOSPITALIZACION",
    "PROCEDIMIENTO",
    "FORMULA",
    "CONTROL",
    "OTRO",
}

SQL_FRAGMENTOS = text(
    f"""
SELECT f.id, f.documento_id, f.orden, f.pagina_inicio, f.pagina_fin, f.seccion,
       f.contenido_texto, f.metadata_jsonb,
       d.nombre_archivo_original, d.tipo_documento, COALESCE(d.numero_adenda, 0) AS numero_adenda,
       d.sha256_original,
       0.0 AS rrf, NULL::bigint AS rango_vectorial, NULL::bigint AS rango_lexico
FROM fragmentos f JOIN documentos d ON d.id = f.documento_id
WHERE {_FILTRO_SEGURO} AND d.tipo_documento <> 'PROSPECTO'
ORDER BY d.uploaded_at, f.orden
LIMIT :limite
"""
)

# Sin límite en SQL: el tope es por documento (`cronologia_max_fragmentos_documento`).
SQL_TODOS = text(
    f"""
SELECT f.id, f.documento_id, f.orden, f.pagina_inicio, f.pagina_fin, f.seccion,
       f.contenido_texto, f.metadata_jsonb,
       d.nombre_archivo_original, d.tipo_documento, COALESCE(d.numero_adenda, 0) AS numero_adenda,
       d.sha256_original,
       0.0 AS rrf, NULL::bigint AS rango_vectorial, NULL::bigint AS rango_lexico
FROM fragmentos f JOIN documentos d ON d.id = f.documento_id
WHERE {_FILTRO_SEGURO} AND d.tipo_documento <> 'PROSPECTO'
  AND (CAST(:documento_id AS uuid) IS NULL OR f.documento_id = :documento_id)
ORDER BY d.uploaded_at, f.documento_id, f.orden
"""
)

SQL_DOCUMENTOS = text(
    f"""
SELECT DISTINCT f.documento_id
FROM fragmentos f JOIN documentos d ON d.id = f.documento_id
WHERE {_FILTRO_SEGURO} AND d.tipo_documento <> 'PROSPECTO'
"""
)

# ---------- Nombres de examen: sinónimos frecuentes en informes de Colombia ----------
# Solo agrupan valores del mismo examen escritos de forma distinta; no dicen nada del examen.
_SINONIMOS = {
    "hemoglobina": ["hemoglobina", "hb", "hgb"],
    "hematocrito": ["hematocrito", "hto", "hct"],
    "leucocitos": ["leucocitos", "globulos blancos", "wbc", "recuento de leucocitos"],
    "plaquetas": ["plaquetas", "plt", "recuento de plaquetas"],
    "glucosa": [
        "glucosa",
        "glicemia",
        "glucemia",
        "glucosa basal",
        "glicemia basal",
        "glucosa en ayunas",
        "glicemia en ayunas",
    ],
    "hba1c": ["hemoglobina glicosilada", "hemoglobina glucosilada", "hba1c", "a1c", "hb a1c"],
    "colesterol total": ["colesterol total", "colesterol"],
    "colesterol ldl": [
        "colesterol ldl",
        "ldl",
        "c-ldl",
        "ldl colesterol",
        "colesterol de baja densidad",
    ],
    "colesterol hdl": [
        "colesterol hdl",
        "hdl",
        "c-hdl",
        "hdl colesterol",
        "colesterol de alta densidad",
    ],
    "trigliceridos": ["trigliceridos", "tg"],
    "creatinina": ["creatinina", "creatinina serica"],
    "nitrogeno ureico": ["nitrogeno ureico", "bun", "nitrogeno ureico en sangre"],
    "acido urico": ["acido urico"],
    "tsh": ["tsh", "hormona estimulante de tiroides", "tirotropina"],
    "t4 libre": ["t4 libre", "t4l", "tiroxina libre"],
    "alt": ["alt", "tgp", "alanino aminotransferasa", "alt (tgp)", "tgp (alt)"],
    "ast": ["ast", "tgo", "aspartato aminotransferasa", "ast (tgo)", "tgo (ast)"],
    "sodio": ["sodio", "na"],
    "potasio": ["potasio", "k"],
    "ferritina": ["ferritina"],
    "vitamina d": ["vitamina d", "25 oh vitamina d", "25-oh vitamina d", "vitamina d 25 oh"],
    "pcr": ["pcr", "proteina c reactiva"],
}
_A_CLAVE = {s: clave for clave, lista in _SINONIMOS.items() for s in lista}


def _norm(t: str) -> str:
    sin = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sin.lower()).strip()


def clave_analito(nombre: str) -> str:
    """El mismo examen escrito de varias formas comparte clave («Hb» y «Hemoglobina» → hemoglobina)."""
    n = re.sub(r"[^a-z0-9 ()-]", "", _norm(nombre)).strip()
    return _A_CLAVE.get(n, n)


# ---------- Fechas: las convierte este código, nunca el modelo ----------
_MESES = {
    "enero": 1, "ene": 1, "febrero": 2, "feb": 2, "marzo": 3, "mar": 3, "abril": 4, "abr": 4,
    "mayo": 5, "may": 5, "junio": 6, "jun": 6, "julio": 7, "jul": 7, "agosto": 8, "ago": 8,
    "septiembre": 9, "setiembre": 9, "sep": 9, "sept": 9, "set": 9, "octubre": 10, "oct": 10,
    "noviembre": 11, "nov": 11, "diciembre": 12, "dic": 12,
}  # fmt: skip
_F_ISO = re.compile(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b")
_F_DMY = re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b")
_F_TEXTO = re.compile(
    r"\b(\d{1,2})[\s-]*(?:de\s+)?([a-z]{3,10})\.?[\s-]*(?:de\s+|del\s+)?(\d{4})\b"
)
_F_MES_ANIO = re.compile(r"\b([a-z]{3,10})\.?[\s-]*(?:de\s+|del\s+)?(\d{4})\b")


def _anio(a: str) -> int:
    n = int(a)
    return n + 2000 if n < 100 else n


def fecha_desde_texto(literal: str) -> date | None:
    """Fecha de un texto escrito como en Colombia (día/mes/año). Si no se entiende sin ambigüedad, None.

    «12/03/2025», «2025-03-12», «12 de marzo de 2025», «12-mar-2025» y «marzo de 2025» (día 1) se
    entienden; «03/12» (sin año) o «31/02/2025» no."""
    t = _norm(literal)
    try:
        if m := _F_ISO.search(t):
            return date(int(m[1]), int(m[2]), int(m[3]))
        if m := _F_DMY.search(t):
            return date(_anio(m[3]), int(m[2]), int(m[1]))
        if (m := _F_TEXTO.search(t)) and m[2] in _MESES:
            return date(int(m[3]), _MESES[m[2]], int(m[1]))
        if (m := _F_MES_ANIO.search(t)) and m[1] in _MESES:
            return date(int(m[2]), _MESES[m[1]], 1)
    except ValueError:
        return None
    return None


def _cifra(valor: str) -> float | None:
    """«13,2» → 13.2; «1.020» → 1020 si parece de miles; «<5» o texto → None."""
    v = _t(valor).replace(" ", "")
    if not re.fullmatch(r"\d+(?:[.,]\d+)*", v):
        return None
    if "," in v and "." in v:
        v = v.replace(".", "").replace(",", ".")
    elif "," in v:
        v = v.replace(",", ".") if v.count(",") == 1 else v.replace(",", "")
    elif v.count(".") > 1 or re.fullmatch(r"\d{1,3}\.\d{3}", v):
        v = v.replace(".", "")
    try:
        return float(v)
    except ValueError:
        return None


def _escrito(sub: str, texto: str) -> bool:
    s = _norm(sub)
    return bool(s) and s in _norm(texto)


_MARCAS = {
    "ALTO": "ALTO",
    "ALTA": "ALTO",
    "H": "ALTO",
    "BAJO": "BAJO",
    "BAJA": "BAJO",
    "L": "BAJO",
    "*": "*",
}
_FIN_DE_DATO = re.compile(r"\n|\.\s|;|\|")


def _marca(marca: str, valor: str, fragmento: str) -> str:
    """La marca solo vale si el documento la imprime JUNTO a ese valor (mismo renglón o frase, justo
    antes o después), no si aparece en otro examen del mismo fragmento."""
    m = _t(marca).upper()
    if m not in _MARCAS or not valor:
        return ""
    patron = re.compile(r"\*" if m == "*" else rf"(?<![a-z]){re.escape(m.lower())}(?![a-z])")
    f = fragmento.lower()
    for ocurrencia in re.finditer(re.escape(valor.lower()), f):
        despues = f[ocurrencia.end() : ocurrencia.end() + 40]
        corte = _FIN_DE_DATO.search(despues)
        despues = despues[: corte.start()] if corte else despues
        antes = f[max(0, ocurrencia.start() - 4) : ocurrencia.start()]
        if patron.search(despues) or patron.search(antes):
            return _MARCAS[m]
    return ""


def huella(documentos: list[uuid.UUID], modelo: str) -> str:
    """Identifica el conjunto de documentos: si no cambia, la línea de tiempo guardada sigue valiendo."""
    ids = ",".join(sorted(str(d) for d in set(documentos)))
    base = f"{extraccion_linea.VERSION}|{modelo}|{ids}"
    return hashlib.sha256(base.encode()).hexdigest()[:32]


async def huella_actual(session: AsyncSession, expediente: Expediente) -> str:
    """Huella de los documentos indexados del expediente (sin prospectos), sin llamar a ningún modelo."""
    filas = await session.scalars(
        SQL_DOCUMENTOS,
        {
            "tenant_id": expediente.tenant_id,
            "expediente_id": expediente.id,
            "modelo": expediente.embedding_model_activo,
        },
    )
    return huella(list(filas), expediente.embedding_model_activo)


@dataclass
class ResultadoCronologia:
    eventos: list[dict] = field(default_factory=list)
    analitos: list[dict] = field(default_factory=list)
    citas: list = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)
    mensaje: str = ""
    sin_evidencia: bool = False
    fragmentos: int = 0
    documentos: int = 0
    huella: str = ""
    modelo_llm: str | None = None
    latencia_ms: int = 0


_RELATIVA = re.compile(
    r"\b(?:en|dentro de|despues de|a los?|cada)\s+(?:\d+|un|una|dos|tres|cuatro|seis)\s+"
    r"(?:dias?|semanas?|mes(?:es)?|anos?)\b"
)


def eventos_de_resultados(valores: list[dict], eventos: list[dict]) -> list[dict]:
    """Un evento «Resultados de laboratorio» por documento y fecha, armado con los valores YA comprobados
    (no lo propone el modelo): así cada toma aparece en la línea aunque el modelo no la liste."""
    ya = {(e["fecha"], e["_doc"]) for e in eventos if e["tipo"] == "EXAMEN" and e["fecha"]}
    grupos: dict[tuple, list[dict]] = {}
    for v in valores:
        if v["fecha"] and (v["fecha"], v["_doc"]) not in ya:
            grupos.setdefault((v["fecha"], v["_doc"]), []).append(v)
    salida = []
    for (fecha, doc), vs in grupos.items():
        nombres = list(dict.fromkeys(v["_nombre"] for v in vs))
        lista = ", ".join(nombres[:4]) + (f" y {len(nombres) - 4} más" if len(nombres) > 4 else "")
        salida.append(
            {
                "fecha": fecha,
                "fechaTexto": vs[0]["fechaTexto"],
                "tipo": "EXAMEN",
                "texto": f"Resultados de laboratorio: {lista}.",
                "cita": min(v["cita"] for v in vs),
                "_doc": doc,
            }
        )
    return salida


def ensamblar(
    datos: dict, evidencias: list[FragmentoRecuperado], umbral: float
) -> tuple[_Citas, list[dict], list[dict], int]:
    """Valida lo propuesto por el modelo contra el texto literal. Devuelve citas, eventos, analitos y
    cuántos elementos se descartaron."""
    citas = _Citas(evidencias, umbral)
    texto_doc: dict[uuid.UUID, str] = {}
    for e in evidencias:
        texto_doc[e.documento_id] = texto_doc.get(e.documento_id, "") + "\n" + e.contenido_texto
    descartados = 0

    def fecha_de(literal: str, e: FragmentoRecuperado) -> tuple[str, date | None]:
        lit = _t(literal)
        if not lit or not _escrito(lit, texto_doc.get(e.documento_id, "")):
            return "", None
        return lit, fecha_desde_texto(lit)

    eventos: list[dict] = []
    vistos_ev: set[tuple] = set()
    for ev in datos.get("eventos") or []:
        ok = citas.agregar(ev.get("fragmento"), ev.get("extracto_literal"))
        texto = " ".join(_t(ev.get("descripcion")).split())[:160]
        if ok is None or not texto:
            descartados += 1
            continue
        n, e = ok
        if garantias.afirma_sin_respaldo(
            texto, e.contenido_texto
        ) or garantias.posologia_sin_respaldo(texto, [e.contenido_texto]):
            descartados += 1
            continue
        fecha_texto, fecha = fecha_de(ev.get("fecha_texto"), e)
        tipo = _t(ev.get("tipo")).upper()
        if not fecha_texto and tipo == "CONTROL":
            # Un control indicado casi nunca trae fecha («control en 3 meses»): vale el plazo si está escrito
            # en el fragmento; si no hay plazo, se conserva igual (la persona pondrá la fecha del recordatorio).
            plazo = _RELATIVA.search(_norm(texto))
            fecha_texto = (
                plazo.group(0)
                if plazo and _escrito(plazo.group(0), e.contenido_texto)
                else SIN_FECHA_ESCRITA
            )
        if not fecha_texto:  # cualquier otro evento sin fecha escrita no va en una línea de tiempo
            descartados += 1
            continue
        clave = (tipo, fecha_texto, _norm(texto))
        if clave in vistos_ev:
            continue
        vistos_ev.add(clave)
        eventos.append(
            {
                "fecha": fecha.isoformat() if fecha else None,
                "fechaTexto": fecha_texto,
                "tipo": tipo if tipo in TIPOS_EVENTO else "OTRO",
                "texto": garantias.atribuir_al_documento(texto),
                "cita": n,
                "_doc": e.documento_id,
            }
        )

    analitos: dict[str, dict] = {}
    vistos_val: dict[tuple, dict] = {}
    for v in datos.get("valores") or []:
        ok = citas.agregar(v.get("fragmento"), v.get("extracto_literal"))
        nombre, valor_texto = _t(v.get("analito")), _t(v.get("valor"))
        cifra = _cifra(valor_texto)
        if ok is None or not nombre or cifra is None:
            descartados += 1
            continue
        n, e = ok
        frag = e.contenido_texto
        unidad, rango = _t(v.get("unidad")), _t(v.get("rango"))
        if (
            not _escrito(nombre, frag)
            or not (garantias.numeros(valor_texto) & garantias.numeros(frag))
            or (unidad and not _escrito(unidad, frag))
            or (rango and garantias.afirma_sin_respaldo(rango, frag))
        ):
            descartados += 1
            continue
        fecha_texto, fecha = fecha_de(v.get("fecha_texto"), e)
        clave = clave_analito(nombre)
        # El mismo valor de la misma cita aparece una sola vez; si se repite, gana la versión con fecha.
        previo = vistos_val.get((clave, valor_texto, n))
        if previo is not None:
            if previo["fechaTexto"] is None and fecha_texto:
                previo["fechaTexto"] = fecha_texto
                previo["fecha"] = fecha.isoformat() if fecha else None
            continue
        grupo = analitos.setdefault(
            clave, {"clave": clave, "nombre": nombre, "unidades": [], "valores": []}
        )
        if unidad and unidad not in grupo["unidades"]:
            grupo["unidades"].append(unidad)
        nuevo = {
            "fecha": fecha.isoformat() if fecha else None,
            "fechaTexto": fecha_texto or None,
            "valor": cifra,
            "valorTexto": valor_texto,
            "unidad": unidad or None,
            "rango": rango or None,
            "marca": _marca(v.get("marca"), valor_texto, frag) or None,
            "cita": n,
        }
        vistos_val[(clave, valor_texto, n)] = nuevo
        grupo["valores"].append(nuevo)
        nuevo["_doc"], nuevo["_nombre"] = e.documento_id, nombre

    todos_valores = [v for g in analitos.values() for v in g["valores"]]
    eventos += eventos_de_resultados(todos_valores, eventos)
    # Fecha de referencia de cada documento: la fecha comprobada que más se repite en sus datos.
    fechas_doc: dict[uuid.UUID, Counter] = {}
    for x in [*eventos, *todos_valores]:
        if x["fecha"]:
            fechas_doc.setdefault(x["_doc"], Counter())[x["fecha"]] += 1
    for ev in eventos:
        # «Control en 3 meses»: no es una fecha. Se ubica junto al documento que lo indica, sin calcular
        # la fecha del control (eso lo confirma la persona en sus recordatorios).
        if (
            not ev["fecha"]
            and (ev["tipo"] == "CONTROL" or _RELATIVA.search(_norm(ev["fechaTexto"])))
            and ev["_doc"] in fechas_doc
        ):
            ev["referencia"] = fechas_doc[ev["_doc"]].most_common(1)[0][0]
    for x in [*eventos, *todos_valores]:
        x.pop("_doc", None)
        x.pop("_nombre", None)

    def orden_fecha(x: dict):
        f = x["fecha"] or x.get("referencia")
        return (f is None, f or "", x["fecha"] is None)

    eventos.sort(key=orden_fecha)
    lista = []
    for g in analitos.values():
        g["valores"].sort(key=orden_fecha)
        # Con unidades distintas no se comparan en una gráfica: el documento las mide distinto.
        g["comparable"] = len(g["unidades"]) <= 1
        lista.append(g)
    # Primero los exámenes con más mediciones fechadas: son los que muestran evolución.
    lista.sort(key=lambda g: (-sum(1 for x in g["valores"] if x["fecha"]), g["nombre"].lower()))
    return citas, eventos, lista, descartados


async def _documentos(
    session: AsyncSession, expediente: Expediente, s: Settings, documento_id: uuid.UUID | None = None
) -> tuple[dict[uuid.UUID, list[FragmentoRecuperado]], int]:
    """Los fragmentos de cada documento (en orden de subida) y cuántos documentos se recortaron."""
    filas = await session.execute(
        SQL_TODOS,
        {
            "tenant_id": expediente.tenant_id,
            "expediente_id": expediente.id,
            "modelo": expediente.embedding_model_activo,
            "documento_id": documento_id,
        },
    )
    grupos: dict[uuid.UUID, list[FragmentoRecuperado]] = {}
    for fila in filas:
        e = _fila(fila)
        grupos.setdefault(e.documento_id, []).append(e)
    tope = max(1, s.cronologia_max_fragmentos_documento)
    recortados = sum(1 for g in grupos.values() if len(g) > tope)
    return {d: g[:tope] for d, g in grupos.items()}, recortados


async def extraer_de_documento(
    session: AsyncSession,
    expediente: Expediente,
    documento_id: uuid.UUID,
    llm: ProveedorLLM,
    s: Settings,
) -> str:
    """Lee un documento recién indexado: «extraida», «ya_estaba» u «omitida» (no tiene qué leer)."""
    grupos, _ = await _documentos(session, expediente, s, documento_id)
    await session.close()  # ninguna conexión retenida mientras el modelo responde
    if not grupos:
        return "omitida"
    if documento_id in await extraccion_linea.vigentes(expediente.tenant_id, grupos):
        return "ya_estaba"
    await extraccion_linea.leer(expediente.tenant_id, expediente.id, grupos, llm, s)
    return "extraida"


async def armar(
    session: AsyncSession,
    expediente: Expediente,
    llm: ProveedorLLM,
    s: Settings,
    huella_docs: str,
    rehacer: bool = False,
) -> ResultadoCronologia:
    t0 = time.perf_counter()
    grupos, recortados = await _documentos(session, expediente, s)
    evidencias = [e for g in grupos.values() for e in g]
    r = ResultadoCronologia(fragmentos=len(evidencias))
    r.documentos = len(grupos)
    r.huella = huella_docs

    def cerrar() -> ResultadoCronologia:
        r.latencia_ms = int((time.perf_counter() - t0) * 1000)
        return r

    if not evidencias:
        r.mensaje, r.sin_evidencia = MENSAJE_SIN_DATOS, True
        return cerrar()

    await session.close()  # ninguna conexión retenida mientras el modelo responde
    lectura = await extraccion_linea.leer(
        expediente.tenant_id, expediente.id, grupos, llm, s, rehacer
    )
    r.modelo_llm = lectura.modelo
    # `ensamblar` identifica cada fragmento por su posición («F3»); lo guardado lo nombra por su UUID.
    posicion = {str(e.id): f"F{i}" for i, e in enumerate(evidencias, start=1)}
    datos = {
        lista: [{**x, "fragmento": posicion.get(x.get("fragmento"), "")} for x in propuestas]
        for lista, propuestas in lectura.datos.items()
    }
    citas, eventos, analitos, descartados = ensamblar(datos, evidencias, s.umbral_confianza_ocr)
    r.eventos, r.analitos, r.citas = eventos, analitos, citas.lista
    if descartados:
        r.alertas.append(
            f"Se omitieron {descartados} dato(s) que no se pudieron comprobar contra el texto de tus documentos."
        )
    if any(x["fecha"] is None and not x.get("referencia") for x in eventos) or any(
        v["fecha"] is None for g in analitos for v in g["valores"]
    ):
        r.alertas.append(
            "Algunas fechas están escritas de una forma que no se puede ubicar sin dudas; se muestran tal como "
            "las trae el documento."
        )
    if any(not g["comparable"] for g in analitos):
        r.alertas.append(
            "Algunos exámenes aparecen con unidades distintas según el documento; no se grafican juntos."
        )
    if recortados:
        r.alertas.append(
            f"{recortados} documento(s) muy largo(s): para la línea de tiempo solo se leyó la primera parte de cada uno."
        )
    if lectura.pendientes:
        r.alertas.append(
            f"No pude leer {lectura.pendientes} documento(s) porque el servicio de IA falló. La línea está "
            "incompleta: vuelve a intentarlo en unos minutos."
        )
        r.huella = ""  # una línea incompleta no se reutiliza
    if not eventos and not analitos:
        r.mensaje, r.sin_evidencia = MENSAJE_SIN_DATOS, True
    return cerrar()


def a_json(r: ResultadoCronologia, consulta_id: uuid.UUID, modelo_embeddings: str) -> dict:
    from app.rag.motor import cita_a_json

    return {
        "consultaId": str(consulta_id),
        "modo": "cronologia",
        "respuestaAnalitica": r.mensaje or "Línea de tiempo de tus documentos.",
        "eventos": r.eventos,
        "analitos": r.analitos,
        "avisoGeneral": AVISO_GENERAL,
        "sinEvidencia": r.sin_evidencia,
        "alertas": r.alertas,
        "citas": [cita_a_json(c) for c in r.citas],
        "huella": r.huella,
        "documentos": r.documentos,
        "modeloEmbeddings": modelo_embeddings,
        "modeloLlm": r.modelo_llm,
        "fragmentosRecuperados": r.fragmentos,
        "latenciaMs": r.latencia_ms,
    }
