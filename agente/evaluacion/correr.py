"""Evaluación de calidad con el proveedor de IA configurado. Uso, desde `agente/` (necesita Docker):

    uv run python -m evaluacion.correr [--salida informe.json] [--pausa 5] [--fijar-base]

Levanta una base PostgreSQL desechable con las migraciones, indexa los documentos INVENTADOS de
`evaluacion/casos.py` con el mismo proceso que la aplicación, hace las preguntas, pide la línea
de tiempo, la explicación y la preparación, y compara cada métrica con su mínimo en
`evaluacion/base.json`.

Gasta llamadas reales del proveedor (unas 20 al modelo, más los embeddings). La clave sale del
entorno o de `agente/.env`, como en la aplicación; nunca se imprime.

Salida: 0 = todo sobre el mínimo; 1 = alguna métrica bajó; 2 = no se pudo evaluar (sin
credenciales o el proveedor no respondió), que no es lo mismo que una caída de calidad.
"""

import argparse
import asyncio
import base64
import json
import os
import secrets
import sys
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.privacidad.anonimizar import enmascarar_texto
from evaluacion import casos, corpus_nombres, metricas
from evaluacion.anonimizacion import medir

METRICAS = (
    "recuperacion",  # el fragmento correcto llega al modelo
    "respuesta",  # la respuesta dice el dato
    "cita",  # una cita del documento correcto contiene el dato
    "cifras_respaldadas",  # las cifras de las respuestas están en sus citas
    "abstencion",  # se abstiene cuando los documentos no lo dicen
    "limites",  # rechaza dosis, qué tomar y diagnóstico
    "linea_encontrados",
    "linea_sin_inventos",
    "linea_eventos",
    "explicacion",
    "preparacion",
    "anonimizacion_nombres",  # conjunto de reserva
    "anonimizacion_sin_tapar_de_mas",
)
BASE = Path(__file__).parent / "base.json"
MIGRACIONES = Path(__file__).resolve().parents[2] / "api-java/src/main/resources/db/migration"


class ProveedorCaido(Exception):
    pass


class Observador:
    """El modelo real, guardando el último prompt para saber qué fragmentos recibió."""

    def __init__(self, llm):
        self.llm = llm
        self.ultimo = ""
        self.modelos: set[str] = set()

    @property
    def modelo(self) -> str:
        return self.llm.modelo

    async def generar_json(self, sistema, prompt, esquema):
        self.ultimo = prompt
        salida = await self.llm.generar_json(sistema, prompt, esquema)
        self.modelos.add(salida.modelo)
        return salida


@dataclass
class Ids:
    tenant: str
    expediente: str
    usuario: str
    documentos: dict[str, str]  # clave de casos.DOCUMENTOS -> id


def token() -> str:
    from app.core.config import get_settings

    return get_settings().internal_token


async def _pedir(
    cliente, ruta: str, cuerpo: dict, cabeceras: dict, intentos=3, espera=30.0
) -> dict:
    for intento in range(1, intentos + 1):
        r = await cliente.post(f"/internal/v1{ruta}", json=cuerpo, headers=cabeceras)
        if r.status_code != 503:
            r.raise_for_status()
            return r.json()
        if intento < intentos:
            await asyncio.sleep(espera)
    raise ProveedorCaido(f"el proveedor de IA no respondió en {ruta} tras {intentos} intentos")


def _tasa(aciertos: float, total: float) -> float:
    return round(aciertos / total, 4) if total else 0.0


async def evaluar(cliente, ids: Ids, observador: Observador, cabeceras: dict, pausa=0.0) -> dict:
    base = {"tenant_id": ids.tenant, "expediente_id": ids.expediente, "usuario_id": ids.usuario}
    fallos: list[str] = []

    async def pedir(ruta: str, **extra) -> dict:
        await asyncio.sleep(pausa)
        return await _pedir(cliente, ruta, base | extra, cabeceras)

    recuperadas = dichas = citadas = cifras_ok = cifras = 0
    for caso in casos.RESPONDIBLES:
        observador.ultimo = ""
        cuerpo = await pedir("/consultas", pregunta=caso.pregunta)
        llego = metricas.normalizar(caso.fragmento) in metricas.normalizar(observador.ultimo)
        dice, cita = metricas.puntuar_respuesta(caso, cuerpo, ids.documentos)
        ok, total = metricas.cifras_respaldadas(cuerpo)
        recuperadas, dichas, citadas = recuperadas + llego, dichas + dice, citadas + cita
        cifras_ok, cifras = cifras_ok + ok, cifras + total
        if not (llego and dice and cita and ok == total):
            fallos.append(
                f"pregunta «{caso.pregunta}»: recuperada={llego} dato={dice} cita={cita} "
                f"cifras={ok}/{total} · respondió: {cuerpo.get('respuestaAnalitica', '')[:300]}"
            )

    abstenidas = 0
    for pregunta in casos.SIN_RESPUESTA:
        cuerpo = await pedir("/consultas", pregunta=pregunta)
        abstenidas += bool(cuerpo.get("sinEvidencia"))
        if not cuerpo.get("sinEvidencia"):
            fallos.append(
                f"debía abstenerse «{pregunta}»: {cuerpo.get('respuestaAnalitica', '')[:300]}"
            )

    rechazadas = 0
    for pregunta in casos.DE_LIMITE:
        cuerpo = await pedir("/consultas", pregunta=pregunta)
        rechazadas += "limiteClinico" in cuerpo
        if "limiteClinico" not in cuerpo:
            fallos.append(f"debía rechazar «{pregunta}»")

    linea = metricas.puntuar_linea(await pedir("/cronologias", rehacer=True))
    fallos += [f"línea de tiempo: {x}" for x in linea["faltan"]]

    explicacion = await pedir(
        "/explicaciones", documento_id=ids.documentos[casos.DOCUMENTO_A_EXPLICAR]
    )
    explicados, faltan = metricas.puntuar_explicacion(explicacion)
    fallos += [f"explicación: falta {x}" for x in faltan]

    preparados, esperados, faltan = metricas.puntuar_preparacion(await pedir("/preparaciones"))
    fallos += [f"preparación: falta {x}" for x in faltan]

    nombres = medir(
        corpus_nombres.RESERVA_NOMBRES + corpus_nombres.RESERVA_SIN_NOMBRES, enmascarar_texto
    )

    n = len(casos.RESPONDIBLES)
    medidas = {
        "recuperacion": _tasa(recuperadas, n),
        "respuesta": _tasa(dichas, n),
        "cita": _tasa(citadas, n),
        # Sin ninguna cifra dicha no hay nada respaldado: no se premia el silencio.
        "cifras_respaldadas": _tasa(cifras_ok, cifras),
        "abstencion": _tasa(abstenidas, len(casos.SIN_RESPUESTA)),
        "limites": _tasa(rechazadas, len(casos.DE_LIMITE)),
        "linea_encontrados": _tasa(*linea["valores"]),
        "linea_sin_inventos": _tasa(*linea["sin_inventos"]),
        "linea_eventos": _tasa(*linea["eventos"]),
        "explicacion": _tasa(explicados, len(casos.EXPLICACION_ESPERADA)),
        "preparacion": _tasa(preparados, esperados),
        "anonimizacion_nombres": round(nombres.cobertura, 4),
        "anonimizacion_sin_tapar_de_mas": round(1 - nombres.tapado_de_mas, 4),
    }
    return {"medidas": medidas, "fallos": fallos, "modelos": sorted(observador.modelos)}


# ---------- Ejecución con el proveedor real ----------
def credenciales() -> bool:
    from app.core.config import Settings

    s = Settings()
    if s.ia_proveedor == "vertex":
        return bool(s.vertex_proyecto)
    return bool(s.gemini_api_key)


def _preparar_entorno(url_admin: str, efimero: str) -> None:
    """Base desechable con el esquema de Flyway y el rol de la aplicación (con RLS en vigor)."""
    import psycopg

    clave = secrets.token_urlsafe(24)
    scripts = sorted(MIGRACIONES.glob("V*__*.sql"), key=lambda p: int(p.name[1:].split("__")[0]))
    with psycopg.connect(url_admin, autocommit=True) as conn:
        for script in scripts:
            conn.execute(script.read_text(encoding="utf-8").replace("${app_password}", clave))
    app_url = url_admin.replace("postgresql://", "postgresql+asyncpg://")
    app_url = app_url.replace(app_url.split("//")[1].split("@")[0], f"medtender_app:{clave}")
    os.environ.update(
        {
            "DATABASE_URL": app_url,
            "TEST_DATABASE_ADMIN_URL": url_admin,  # lo usa `tests.fakes.subir`, que hace de API
            "EPHEMERAL_DIR": efimero,
            "ENTORNO": "desarrollo",
            "INTERNAL_TOKEN": secrets.token_urlsafe(48),
            "BARRIDO_HABILITADO": "false",
            "COLA_BACKEND": "ninguna",
            "REDIS_URL": "redis://127.0.0.1:1/0",
            "DB_NULL_POOL": "true",
            "DATOS_CLAVE": base64.b64encode(os.urandom(32)).decode(),
        }
    )


def _sembrar_persona(url_admin: str, modelo: str) -> tuple[str, str, str]:
    import psycopg

    tenant, usuario, expediente = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(url_admin) as conn:
        conn.execute(
            "INSERT INTO tenants (id, nombre, nit, tipo) VALUES (%s, 'Evaluación', %s, 'PERSONAL')",
            (tenant, f"EVAL-{tenant.hex[:12]}"),
        )
        conn.execute(
            "INSERT INTO usuarios (id, tenant_id, email, password_hash, "
            "nombre_completo, rol_global) "
            "VALUES (%s, %s, 'evaluacion@example.com', 'sin-uso', 'Evaluación', 'ADMIN_TENANT')",
            (usuario, tenant),
        )
        conn.execute(
            "INSERT INTO expedientes (id, tenant_id, codigo_expediente, "
            "titulo, entidad_contratante, "
            "tipo_expediente, embedding_model_activo, embedding_dimension, created_by) VALUES "
            "(%s, %s, 'EVAL', 'Evaluación', 'Evaluación', 'LICITACION_MEDICAMENTOS', %s, 1536, %s)",
            (expediente, tenant, modelo, usuario),
        )
    return str(tenant), str(expediente), str(usuario)


async def _evaluar_real(url_admin: str, pausa: float) -> dict:
    from httpx import ASGITransport, AsyncClient

    from app.core.config import get_settings
    from app.core.db import get_engine, get_sessionmaker
    from app.ia.embeddings import get_router
    from app.ia.llm import get_llm
    from app.main import create_app
    from app.pipeline.procesador import procesar_documento
    from app.pipeline.vectorizacion import VectorizadorEmbeddings
    from tests.fakes import subir
    from tests.pdfs import pdf_texto

    modelo = get_settings().embedding_model_default
    tenant, expediente, usuario = _sembrar_persona(url_admin, modelo)
    documentos = {}
    with ThreadPoolExecutor(max_workers=1) as ejecutor:
        for clave, texto in casos.DOCUMENTOS.items():
            r = await subir(
                expediente, pdf_texto([texto]), tipo="HISTORIA_CLINICA", nombre=f"{clave}.pdf"
            )
            documentos[clave] = r.json()["id"]
            await procesar_documento(
                get_sessionmaker(), uuid.UUID(documentos[clave]), ejecutor,
                VectorizadorEmbeddings(get_router()),
            )  # fmt: skip
    observador = Observador(get_llm())
    app = create_app()
    app.dependency_overrides[get_llm] = lambda: observador
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://evaluacion") as c:
            return await evaluar(
                c, Ids(tenant, expediente, usuario, documentos), observador,
                {"X-Internal-Token": token()}, pausa,
            )  # fmt: skip
    finally:
        await get_engine().dispose()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m evaluacion.correr", description=__doc__)
    p.add_argument("--salida", help="Escribe el informe en este archivo JSON")
    p.add_argument("--pausa", type=float, default=0.0, help="Segundos entre llamadas (cuotas)")
    p.add_argument(
        "--fijar-base",
        action="store_true",
        help="Guarda como mínimos lo medido menos un margen de 10 puntos (revisar antes de subir)",
    )
    args = p.parse_args(argv)
    if not credenciales():
        print(
            "No se evaluó: faltan las credenciales del proveedor de IA (GEMINI_API_KEY o Vertex)."
        )
        return 2

    from testcontainers.community.postgres import PostgresContainer

    with (
        PostgresContainer("pgvector/pgvector:pg16", driver=None) as pg,
        tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as efimero,
    ):
        url = pg.get_connection_url()
        _preparar_entorno(url, efimero)
        from app.core.config import get_settings

        get_settings.cache_clear()
        try:
            informe = asyncio.run(_evaluar_real(url, args.pausa))
        except ProveedorCaido as exc:
            print(f"No se evaluó: {exc}.")
            return 2

    base = json.loads(BASE.read_text(encoding="utf-8"))
    avisos = metricas.comparar(informe["medidas"], base["minimos"])
    informe |= {"fecha": datetime.now(UTC).isoformat(timespec="seconds"), "por_debajo": avisos}
    for nombre in METRICAS:
        print(
            f"{nombre:32} {informe['medidas'][nombre]:6.0%}  (mínimo {base['minimos'][nombre]:.0%})"
        )
    print("Modelos:", ", ".join(informe["modelos"]) or "ninguno")
    for fallo in informe["fallos"]:
        print("  ·", fallo)
    if args.salida:
        Path(args.salida).write_text(
            json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if args.fijar_base:
        fijos = {"limites", "anonimizacion_nombres", "anonimizacion_sin_tapar_de_mas"}
        for nombre in set(METRICAS) - fijos:
            base["minimos"][nombre] = max(0.0, round(informe["medidas"][nombre] - 0.1, 2))
        base["medido"] = {"fecha": informe["fecha"], "modelos": informe["modelos"]}
        BASE.write_text(json.dumps(base, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("RESULTADO:", "alguna métrica bajó" if avisos else "todo sobre el mínimo")
    for aviso in avisos:
        print("  ✗", aviso)
    return 1 if avisos else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
