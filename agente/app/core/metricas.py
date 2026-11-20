"""Métricas Prometheus.

Dos tipos:
- Contadores e histogramas del proceso de la API (HTTP y consultas).
- Medidores del estado del negocio, calculados desde PostgreSQL en cada scrape. Así reflejan lo
  que hace también el worker, que es otro proceso con su propia memoria.

La API corre con un solo proceso uvicorn (asyncio); con varios habría que usar el modo
multiproceso de prometheus_client.
"""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ActaPurga, Consulta, Documento, Fragmento, Reindexacion

REGISTRO = CollectorRegistry()

HTTP_SOLICITUDES = Counter(
    "medtender_http_solicitudes_total",
    "Solicitudes HTTP atendidas",
    ["metodo", "ruta", "codigo"],
    registry=REGISTRO,
)
HTTP_DURACION = Histogram(
    "medtender_http_duracion_segundos",
    "Duración de las solicitudes HTTP",
    ["metodo", "ruta"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
    registry=REGISTRO,
)
CONSULTAS = Counter(
    "medtender_consultas_total",
    "Consultas RAG",
    ["resultado"],  # con_evidencia | sin_evidencia | error_ia
    registry=REGISTRO,
)
CONSULTA_DURACION = Histogram(
    "medtender_consulta_duracion_segundos",
    "Duración de una consulta RAG de punta a punta",
    buckets=(0.5, 1, 2, 3, 5, 8, 13, 21, 34, 60),
    registry=REGISTRO,
)
LLM_RESPUESTAS = Counter(
    "medtender_llm_respuestas_total",
    "Respuestas del modelo generativo por modelo",
    ["modelo"],
    registry=REGISTRO,
)

DOCUMENTOS = Gauge("medtender_documentos", "Documentos por estado", ["estado"], registry=REGISTRO)
DOCUMENTOS_ATASCADOS = Gauge(
    "medtender_documentos_en_proceso_mas_de_1h",
    "Documentos que llevan más de una hora en un estado no final",
    registry=REGISTRO,
)
TEMPORALES_PENDIENTES = Gauge(
    "medtender_pdf_temporales_pendientes",
    "Documentos cuyo PDF temporal aún no se ha purgado",
    registry=REGISTRO,
)
PURGAS = Gauge("medtender_purgas", "Actas de purga por motivo", ["motivo"], registry=REGISTRO)
FRAGMENTOS = Gauge("medtender_fragmentos", "Fragmentos indexados", registry=REGISTRO)
REINDEXACIONES = Gauge(
    "medtender_reindexaciones", "Reindexaciones por estado", ["estado"], registry=REGISTRO
)
CONSULTAS_24H = Gauge(
    "medtender_consultas_ultimas_24h", "Consultas RAG registradas en 24 h", registry=REGISTRO
)

_ESTADOS_FINALES = ("INDEXADO_Y_PURGADO", "ERROR_PURGADO", "INDEXADO_PENDIENTE_PURGA")


async def actualizar_medidores(session: AsyncSession) -> None:
    for g in (DOCUMENTOS, PURGAS, REINDEXACIONES):
        g.clear()
    for estado, n in (
        await session.execute(
            select(Documento.estado_indexacion, func.count()).group_by(Documento.estado_indexacion)
        )
    ).all():
        DOCUMENTOS.labels(estado).set(n)
    for motivo, n in (
        await session.execute(select(ActaPurga.motivo, func.count()).group_by(ActaPurga.motivo))
    ).all():
        PURGAS.labels(motivo).set(n)
    for estado, n in (
        await session.execute(
            select(Reindexacion.estado, func.count()).group_by(Reindexacion.estado)
        )
    ).all():
        REINDEXACIONES.labels(estado).set(n)

    FRAGMENTOS.set(await session.scalar(select(func.count()).select_from(Fragmento)) or 0)
    DOCUMENTOS_ATASCADOS.set(
        await session.scalar(
            select(func.count())
            .select_from(Documento)
            .where(
                Documento.estado_indexacion.not_in(_ESTADOS_FINALES),
                Documento.estado_actualizado_at < func.now() - text("interval '1 hour'"),
            )
        )
        or 0
    )
    TEMPORALES_PENDIENTES.set(
        await session.scalar(
            select(func.count())
            .select_from(Documento)
            .where(
                Documento.temp_file_purged.is_(False),
                Documento.estado_indexacion != "ERROR_PURGADO",
            )
        )
        or 0
    )
    CONSULTAS_24H.set(
        await session.scalar(
            select(func.count())
            .select_from(Consulta)
            .where(Consulta.created_at > func.now() - text("interval '24 hours'"))
        )
        or 0
    )
