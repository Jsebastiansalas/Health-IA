"""Recuperación híbrida (Pasos 12 y 13).

1. Seguridad primero: cada CTE filtra por tenant_id, expediente_id, el modelo de embeddings
   activo y documentos ya indexados. No hay forma de llamar a esta búsqueda sin esos filtros.
2. Una sola consulta SQL combina el Top-K vectorial (pgvector, distancia coseno) y el Top-K
   léxico (tsvector 'spanish', ts_rank_cd) con Reciprocal Rank Fusion:
       rrf(d) = Σ 1 / (k + rango_i(d))
3. Reranking de dominio: los fragmentos de ADENDAS reciben un boost (mayor número de adenda
   primero en caso de empate) para advertir cuando modifican el pliego.
4. Expansión contextual: se añaden los vecinos orden±1 de las mejores evidencias para no cortar
   cláusulas ni tablas a la mitad.

Nota sobre la rama léxica: websearch_to_tsquery exige TODAS las palabras (AND); con preguntas
en lenguaje natural casi nunca hay coincidencias. Se usa un OR de los lexemas de la pregunta y
ts_rank_cd premia a los fragmentos que contienen más términos. Los códigos exactos (CUM,
UNSPSC, INVIMA, CIE-10, "Adenda 02") siguen coincidiendo porque son lexemas propios.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ia.embeddings import a_columna

_FILTRO_SEGURO = """
    f.tenant_id = :tenant_id
    AND f.expediente_id = :expediente_id
    AND f.embedding_model = :modelo
    AND f.embedding IS NOT NULL
    AND d.estado_indexacion IN ('INDEXADO_Y_PURGADO', 'INDEXADO_PENDIENTE_PURGA')
"""

SQL_HIBRIDA = text(
    f"""
WITH consulta_ts AS (
    SELECT CASE WHEN COUNT(*) = 0 THEN NULL
                ELSE to_tsquery('simple', string_agg(quote_literal(lexeme), ' | '))
           END AS q
    FROM unnest(to_tsvector('spanish', :texto))
),
vectorial AS (
    SELECT f.id,
           ROW_NUMBER() OVER (ORDER BY f.embedding <=> CAST(:vector AS vector)) AS rango
    FROM fragmentos f JOIN documentos d ON d.id = f.documento_id
    WHERE {_FILTRO_SEGURO}
    ORDER BY f.embedding <=> CAST(:vector AS vector)
    LIMIT :top_k
),
lexico AS (
    SELECT f.id,
           ROW_NUMBER() OVER (ORDER BY ts_rank_cd(f.fts_vector, c.q) DESC, f.id) AS rango
    FROM fragmentos f JOIN documentos d ON d.id = f.documento_id, consulta_ts c
    WHERE {_FILTRO_SEGURO} AND c.q IS NOT NULL AND f.fts_vector @@ c.q
    ORDER BY ts_rank_cd(f.fts_vector, c.q) DESC, f.id
    LIMIT :top_k
),
fusion AS (
    SELECT COALESCE(v.id, l.id) AS id,
           COALESCE(1.0 / (:rrf_k + v.rango), 0) + COALESCE(1.0 / (:rrf_k + l.rango), 0) AS rrf,
           v.rango AS rango_vectorial,
           l.rango AS rango_lexico
    FROM vectorial v FULL OUTER JOIN lexico l ON v.id = l.id
)
SELECT f.id, f.documento_id, f.orden, f.pagina_inicio, f.pagina_fin, f.seccion,
       f.contenido_texto, f.metadata_jsonb,
       d.nombre_archivo_original, d.tipo_documento, COALESCE(d.numero_adenda, 0) AS numero_adenda,
       d.sha256_original,
       fu.rrf, fu.rango_vectorial, fu.rango_lexico
FROM fusion fu
JOIN fragmentos f ON f.id = fu.id
JOIN documentos d ON d.id = f.documento_id
ORDER BY fu.rrf DESC
"""
)

SQL_VECINOS = text(
    f"""
SELECT f.id, f.documento_id, f.orden, f.pagina_inicio, f.pagina_fin, f.seccion,
       f.contenido_texto, f.metadata_jsonb,
       d.nombre_archivo_original, d.tipo_documento, COALESCE(d.numero_adenda, 0) AS numero_adenda,
       d.sha256_original,
       0.0 AS rrf, NULL::bigint AS rango_vectorial, NULL::bigint AS rango_lexico
FROM fragmentos f JOIN documentos d ON d.id = f.documento_id
JOIN unnest(CAST(:documentos AS uuid[]), CAST(:ordenes AS int[])) AS buscado(documento_id, orden)
  ON buscado.documento_id = f.documento_id AND buscado.orden = f.orden
WHERE {_FILTRO_SEGURO}
"""
)


@dataclass
class FragmentoRecuperado:
    id: uuid.UUID
    documento_id: uuid.UUID
    orden: int
    pagina_inicio: int
    pagina_fin: int
    seccion: str
    contenido_texto: str
    metadata: dict
    nombre_archivo: str
    tipo_documento: str
    numero_adenda: int
    sha256_original: str
    rrf: float = 0.0
    rango_vectorial: int | None = None
    rango_lexico: int | None = None
    puntaje: float = 0.0
    vecinos: list["FragmentoRecuperado"] = field(default_factory=list)

    @property
    def es_adenda(self) -> bool:
        return self.tipo_documento == "ADENDA"


def _fila(row) -> FragmentoRecuperado:
    m = row._mapping
    return FragmentoRecuperado(
        id=m["id"],
        documento_id=m["documento_id"],
        orden=m["orden"],
        pagina_inicio=m["pagina_inicio"],
        pagina_fin=m["pagina_fin"],
        seccion=m["seccion"],
        contenido_texto=m["contenido_texto"],
        metadata=m["metadata_jsonb"] or {},
        nombre_archivo=m["nombre_archivo_original"],
        tipo_documento=m["tipo_documento"],
        numero_adenda=m["numero_adenda"],
        sha256_original=m["sha256_original"],
        rrf=float(m["rrf"]),
        rango_vectorial=m["rango_vectorial"],
        rango_lexico=m["rango_lexico"],
    )


def reordenar(
    candidatos: list[FragmentoRecuperado], boost_adenda: float
) -> list[FragmentoRecuperado]:
    """Reranking de dominio: adendas primero ante relevancia similar, la más reciente arriba."""
    for c in candidatos:
        c.puntaje = c.rrf * (1 + boost_adenda) if c.es_adenda else c.rrf
    return sorted(candidatos, key=lambda c: (c.puntaje, c.numero_adenda), reverse=True)


async def busqueda_hibrida(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    expediente_id: uuid.UUID,
    modelo: str,
    vector: list[float],
    texto: str,
    top_k: int = 20,
    rrf_k: int = 60,
    ef_search: int = 100,
) -> list[FragmentoRecuperado]:
    # pgvector >= 0.8: con filtros, el escaneo iterativo evita devolver menos de top_k
    # resultados cuando el expediente es una fracción pequeña de la tabla.
    await session.execute(text("SET LOCAL hnsw.iterative_scan = 'relaxed_order'"))
    await session.execute(text(f"SET LOCAL hnsw.ef_search = {int(ef_search)}"))
    filas = await session.execute(
        SQL_HIBRIDA,
        {
            "tenant_id": tenant_id,
            "expediente_id": expediente_id,
            "modelo": modelo,
            "vector": str(a_columna(vector)),
            "texto": texto,
            "top_k": top_k,
            "rrf_k": rrf_k,
        },
    )
    return [_fila(r) for r in filas]


async def expandir_vecinos(
    session: AsyncSession,
    evidencias: list[FragmentoRecuperado],
    *,
    tenant_id: uuid.UUID,
    expediente_id: uuid.UUID,
    modelo: str,
) -> None:
    """Adjunta a cada evidencia sus vecinos orden-1 y orden+1 que no sean ya evidencias."""
    ya = {(e.documento_id, e.orden) for e in evidencias}
    buscados = sorted(
        {
            (e.documento_id, e.orden + delta)
            for e in evidencias
            for delta in (-1, 1)
            if e.orden + delta >= 1 and (e.documento_id, e.orden + delta) not in ya
        }
    )
    if not buscados:
        return
    filas = await session.execute(
        SQL_VECINOS,
        {
            "tenant_id": tenant_id,
            "expediente_id": expediente_id,
            "modelo": modelo,
            "documentos": [d for d, _ in buscados],
            "ordenes": [o for _, o in buscados],
        },
    )
    vecinos = {(v.documento_id, v.orden): v for v in map(_fila, filas)}
    asignados: set[tuple[uuid.UUID, int]] = set()
    for e in evidencias:
        for delta in (-1, 1):
            clave = (e.documento_id, e.orden + delta)
            if clave in vecinos and clave not in asignados:
                e.vecinos.append(vecinos[clave])
                asignados.add(clave)
        e.vecinos.sort(key=lambda v: v.orden)
