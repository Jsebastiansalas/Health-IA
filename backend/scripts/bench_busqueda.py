"""Benchmark de la búsqueda híbrida (RRF) con muchos fragmentos y varios tenants.

Crea una base de datos DESECHABLE en el PostgreSQL indicado (nunca toca la de la aplicación),
la llena con vectores aleatorios de 1536 dimensiones y mide la consulta real de
`app.rag.busqueda.busqueda_hibrida` en tres escenarios:

  * expediente normal (cientos de fragmentos) entre decenas de tenants: el planificador usa el
    índice (tenant, expediente) y ordena en exacto;
  * tenant pequeño (200 fragmentos) rodeado de cientos de miles ajenos;
  * expediente GIGANTE (decenas de miles de fragmentos): aquí sí entra el índice HNSW con filtro
    y se mide su recall frente a la búsqueda exacta (con y sin hnsw.iterative_scan).

    uv run python scripts/bench_busqueda.py \
        --admin-url postgresql://medtender:medtender@localhost:5434/postgres \
        --fragmentos 100000 --gigante 40000 --tenants 50
"""

import argparse
import asyncio
import math
import os
import random
import statistics
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psycopg

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

MODELO = "gemini-embedding-001"
# OJO: la subconsulta DEBE depender de la fila (`n * 0`). Si no, PostgreSQL la evalúa una sola vez
# por sentencia y todos los fragmentos reciben el MISMO vector (distancias 0, recall trivial).
VECTOR_SQL = (
    "l2_normalize(ARRAY(SELECT random() - 0.5 + n * 0 FROM generate_series(1, 1536))::vector)"
)


def preparar_base(admin_url: str, nombre: str) -> str:
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{nombre}"')
        c.execute(f'CREATE DATABASE "{nombre}"')
    base, _, _ = admin_url.rpartition("/")
    url = f"{base}/{nombre}"
    env = {
        **os.environ,
        "DATABASE_URL": url.replace("postgresql://", "postgresql+asyncpg://"),
        "JWT_SECRET": "x" * 40,
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env=env,
        check=True,
        capture_output=True,
    )
    return url


def insertar_fragmentos(c, filas_sql: str, params: tuple) -> None:
    c.execute(
        f"""
        INSERT INTO fragmentos (tenant_id, expediente_id, documento_id, orden, pagina_inicio,
                                pagina_fin, seccion, contenido_texto, contenido_vectorizado,
                                token_count, embedding_model, embedding)
        {filas_sql}
        """,
        params,
    )


def cargar(url: str, fragmentos: int, tenants: int, gigante: int) -> dict:
    with psycopg.connect(url, autocommit=True) as c:
        t0 = time.perf_counter()
        c.execute(
            "INSERT INTO tenants (id, nombre, nit) SELECT uuid_generate_v4(), 'T' || g, 'NIT' || g "
            "FROM generate_series(1, %s) g",
            (tenants + 1,),
        )
        c.execute(
            "INSERT INTO usuarios (tenant_id, email, password_hash, nombre_completo, rol_global) "
            "SELECT id, nombre || '@x.co', 'x', nombre, 'ADMIN_TENANT' FROM tenants"
        )
        c.execute(
            "INSERT INTO expedientes (tenant_id, codigo_expediente, titulo, tipo_expediente, created_by) "
            "SELECT t.id, 'E' || e, 'Exp ' || e, 'LICITACION_MEDICAMENTOS', u.id "
            "FROM tenants t JOIN usuarios u ON u.tenant_id = t.id, generate_series(1, 3) e"
        )
        c.execute(
            "INSERT INTO documentos (tenant_id, expediente_id, nombre_archivo_original, tipo_documento, "
            "sha256_original, tamano_bytes, estado_indexacion, embedding_model, total_chunks_esperados) "
            "SELECT tenant_id, id, 'Pliego.pdf', 'PLIEGO', repeat('a', 64), 1000, 'INDEXADO_Y_PURGADO', %s, 0 "
            "FROM expedientes",
            (MODELO,),
        )
        docs = c.execute("SELECT count(*) FROM documentos").fetchone()[0]
        # El tenant de nombre más alto es el "pequeño"; se excluye de la carga general.
        pequeno = c.execute(
            "SELECT t.id, e.id, d.id FROM tenants t JOIN expedientes e ON e.tenant_id = t.id "
            "JOIN documentos d ON d.expediente_id = e.id ORDER BY t.nombre DESC, e.codigo_expediente LIMIT 1"
        ).fetchone()
        t_peq, e_peq, d_peq = pequeno
        n_por_doc = max(1, fragmentos // (docs - 3))
        print(f"  tenants={tenants + 1} documentos={docs} fragmentos/doc={n_por_doc}")
        insertar_fragmentos(
            c,
            f"""
            SELECT d.tenant_id, d.expediente_id, d.id, n, n / 4 + 1, n / 4 + 1, 'CLÁUSULA ' || n,
                   'El oferente deberá acreditar el registro sanitario INVIMA vigente para el ítem '
                   || n || ', código UNSPSC ' || (42000000 + n %% 997)
                   || ', con garantía de ' || (6 + n %% 24) || ' meses.',
                   'x', 120, %s, {VECTOR_SQL}
            FROM documentos d, generate_series(1, %s) n
            WHERE d.tenant_id <> %s
            """,
            (MODELO, n_por_doc, t_peq),
        )
        normal = c.execute(
            "SELECT tenant_id, expediente_id FROM fragmentos GROUP BY 1, 2 ORDER BY 1, 2 LIMIT 1"
        ).fetchone()

        # Tenant pequeño: 200 fragmentos, uno de ellos (#77) será el objetivo de la prueba exacta.
        insertar_fragmentos(
            c,
            f"""
            SELECT %s::uuid, %s::uuid, %s::uuid, n, 1, 1, 'SECCIÓN ' || n,
                   'Texto genérico número ' || n, 'x', 10, %s, {VECTOR_SQL}
            FROM generate_series(1, 200) n
            """,
            (t_peq, e_peq, d_peq, MODELO),
        )
        obj_peq = c.execute(
            "SELECT embedding::text FROM fragmentos WHERE expediente_id = %s AND orden = 77",
            (e_peq,),
        ).fetchone()[0]

        # Expediente gigante: un único expediente con decenas de miles de fragmentos.
        t_gig, e_gig = c.execute(
            "SELECT tenant_id, id FROM expedientes WHERE tenant_id <> %s ORDER BY tenant_id, id LIMIT 1 OFFSET 7",
            (t_peq,),
        ).fetchone()
        d_gig = c.execute(
            "INSERT INTO documentos (tenant_id, expediente_id, nombre_archivo_original, tipo_documento, "
            "sha256_original, tamano_bytes, estado_indexacion, embedding_model, total_chunks_esperados) "
            "VALUES (%s, %s, 'Gigante.pdf', 'PLIEGO', repeat('b', 64), 1000, 'INDEXADO_Y_PURGADO', %s, 0) "
            "RETURNING id",
            (t_gig, e_gig, MODELO),
        ).fetchone()[0]
        insertar_fragmentos(
            c,
            f"""
            SELECT %s::uuid, %s::uuid, %s::uuid, n, n / 4 + 1, n / 4 + 1, 'CLÁUSULA ' || n,
                   'Cláusula gigante ' || n || ' sobre garantías y pólizas del contrato.',
                   'x', 120, %s, {VECTOR_SQL}
            FROM generate_series(1, %s) n
            """,
            (t_gig, e_gig, d_gig, MODELO, gigante),
        )
        obj_gig = c.execute(
            "SELECT embedding::text FROM fragmentos WHERE documento_id = %s AND orden = %s",
            (d_gig, gigante // 2),
        ).fetchone()[0]
        print(f"  carga de datos: {time.perf_counter() - t0:.0f}s")

        t0 = time.perf_counter()
        c.execute("DROP INDEX idx_fragmentos_embedding_hnsw")
        c.execute(
            "CREATE INDEX idx_fragmentos_embedding_hnsw ON fragmentos USING hnsw "
            "(embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
        )
        print(f"  índice HNSW construido en {time.perf_counter() - t0:.0f}s")
        c.execute("ANALYZE fragmentos")
        total = c.execute("SELECT count(*) FROM fragmentos").fetchone()[0]
        tam = c.execute("SELECT pg_size_pretty(pg_total_relation_size('fragmentos'))").fetchone()[0]
        print(f"  fragmentos totales={total:,}  tabla+índices={tam}")
    return {
        "normal": normal,
        "pequeno": (t_peq, e_peq),
        "gigante": (t_gig, e_gig),
        "obj_pequeno": obj_peq,
        "obj_gigante": obj_gig,
        "orden_gigante": gigante // 2,
    }


def aleatorio() -> list[float]:
    v = [random.random() - 0.5 for _ in range(1536)]
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def vec(texto: str) -> list[float]:
    return [float(x) for x in texto.strip("[]").split(",")]


def pct(datos: list[float], p: float) -> float:
    datos = sorted(datos)
    return datos[min(len(datos) - 1, int(len(datos) * p))]


async def medir(url: str, ids: dict, repeticiones: int, concurrencia: int) -> None:
    os.environ["DATABASE_URL"] = url.replace("postgresql://", "postgresql+asyncpg://")
    os.environ["JWT_SECRET"] = "x" * 40
    from sqlalchemy import text as sqltext
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.rag import busqueda

    engine = create_async_engine(os.environ["DATABASE_URL"], pool_size=concurrencia + 2)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    async def una(tenant, exp, vector, texto, **kw):
        async with sm() as s:
            t0 = time.perf_counter()
            r = await busqueda.busqueda_hibrida(
                s,
                tenant_id=tenant,
                expediente_id=exp,
                modelo=MODELO,
                vector=vector,
                texto=texto,
                **kw,
            )
            return (time.perf_counter() - t0) * 1000, r

    def resumen(nombre, ms):
        print(
            f"  {nombre:42} p50={statistics.median(ms):6.1f} ms  p95={pct(ms, 0.95):6.1f} ms  "
            f"p99={pct(ms, 0.99):6.1f} ms  máx={max(ms):6.1f} ms"
        )

    textos = [
        "¿Qué registro sanitario INVIMA se exige para el ítem 25?",
        "garantía mínima de los productos",
        "código UNSPSC 42000123 plazo de entrega",
    ]
    escenarios = {
        "expediente normal (~700 fragmentos)": ids["normal"],
        "tenant pequeño (200 entre todos los ajenos)": ids["pequeno"],
        "expediente GIGANTE": ids["gigante"],
    }

    print("\nLatencia secuencial (consulta híbrida completa: vectorial + léxica + RRF)")
    for nombre, (t, e) in escenarios.items():
        await una(t, e, aleatorio(), textos[0])  # calentamiento
        ms, tamanos = [], []
        for i in range(repeticiones):
            lat, r = await una(t, e, aleatorio(), textos[i % 3])
            ms.append(lat)
            tamanos.append(len(r))
        resumen(nombre, ms)
        print(f"      resultados por consulta: min={min(tamanos)} máx={max(tamanos)}")

    # Exactitud: se busca un fragmento con SU PROPIO vector (distancia 0) y un texto sin términos
    # en común, de modo que solo decide la rama vectorial. Debe quedar siempre en primer lugar.
    print("\nExactitud y latencia por modo de hnsw.iterative_scan (consulta con el vector exacto)")
    for expediente, nombre in (
        (ids["pequeno"], "tenant pequeño"),
        (ids["gigante"], "expediente gigante"),
    ):
        async with sm() as s:
            objetivos = (
                await s.execute(
                    sqltext(
                        "SELECT orden, embedding::text FROM fragmentos WHERE tenant_id = :t "
                        "AND expediente_id = :e ORDER BY random() LIMIT 12"
                    ),
                    {"t": expediente[0], "e": expediente[1]},
                )
            ).all()
        for modo in ("strict_order", "relaxed_order"):
            aciertos, ms = 0, []
            for orden, emb in objetivos:
                lat, r = await una(*expediente, vec(emb), "zzzz", iterative=modo)
                ms.append(lat)
                aciertos += r[0].orden == orden
            print(
                f"  {nombre:20} {modo:14} fragmento propio en 1.er lugar: {aciertos}/{len(objetivos)}"
                f"   p50={statistics.median(ms):6.1f} ms"
            )
    r = r  # el último resultado se usa abajo para comprobar el aislamiento entre tenants
    # Aislamiento: nada de lo devuelto puede pertenecer a otro tenant.
    async with sm() as s:
        ajenos = await s.scalar(
            sqltext("SELECT count(*) FROM fragmentos WHERE id = ANY(:ids) AND tenant_id <> :t"),
            {"ids": [x.id for x in r], "t": ids["gigante"][0]},
        )
    print(f"  fragmentos de otros tenants en el resultado: {ajenos} (debe ser 0)")

    # Recall del HNSW en el expediente gigante contra la búsqueda exacta.
    print("\nRecall@20 del índice HNSW en el expediente gigante (vs. búsqueda exacta)")
    t_g, e_g = ids["gigante"]

    async def top20(vector, modo):
        async with sm() as s:
            if modo == "exacta":
                await s.execute(sqltext("SET LOCAL enable_indexscan = off"))
                await s.execute(sqltext("SET LOCAL enable_bitmapscan = off"))
            elif modo == "sin_iterativo":
                await s.execute(sqltext("SET LOCAL hnsw.iterative_scan = 'off'"))
                await s.execute(sqltext("SET LOCAL hnsw.ef_search = 100"))
                await s.execute(sqltext("SET LOCAL enable_bitmapscan = off"))
            else:  # lo que hace la aplicación
                await s.execute(sqltext("SET LOCAL hnsw.iterative_scan = 'relaxed_order'"))
                await s.execute(sqltext("SET LOCAL hnsw.ef_search = 100"))
                await s.execute(sqltext("SET LOCAL enable_bitmapscan = off"))
            filas = await s.execute(
                sqltext(
                    "SELECT id FROM fragmentos WHERE tenant_id = :t AND expediente_id = :e "
                    "AND embedding_model = :m ORDER BY embedding <=> CAST(:v AS vector) LIMIT 20"
                ),
                {"t": t_g, "e": e_g, "m": MODELO, "v": str(vector)},
            )
            return [f for (f,) in filas]

    consultas = [aleatorio() for _ in range(15)]
    exactas = [await top20(v, "exacta") for v in consultas]
    for modo, etiqueta in (
        ("sin_iterativo", "HNSW sin iterative_scan"),
        ("app", "HNSW con iterative_scan (aplicación)"),
    ):
        recalls, devueltos = [], []
        for v, ex in zip(consultas, exactas, strict=True):
            got = await top20(v, modo)
            devueltos.append(len(got))
            recalls.append(len(set(got) & set(ex)) / 20)
        print(
            f"  {etiqueta:40} recall@20={statistics.mean(recalls):.0%}  "
            f"resultados devueltos: min={min(devueltos)} (de 20)"
        )
    print("  (con vectores aleatorios, sin estructura, el recall de HNSW es el peor caso;")
    print("   los embeddings reales forman grupos y suelen rendir mejor)")

    print(f"\nConcurrencia: {concurrencia} consultas simultáneas, expediente normal")
    lat: list[float] = []
    t_n, e_n = ids["normal"]

    async def trabajador():
        for i in range(max(1, repeticiones // concurrencia)):
            ms_, _ = await una(t_n, e_n, aleatorio(), textos[i % 3])
            lat.append(ms_)

    t0 = time.perf_counter()
    await asyncio.gather(*[trabajador() for _ in range(concurrencia)])
    dur = time.perf_counter() - t0
    resumen("bajo concurrencia", lat)
    print(f"      rendimiento: {len(lat) / dur:.0f} consultas/s")

    async with sm() as s:
        await s.execute(sqltext("SET LOCAL hnsw.iterative_scan = 'relaxed_order'"))
        plan = await s.execute(
            sqltext(
                "EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF, SUMMARY ON) SELECT f.id FROM fragmentos f "
                "WHERE f.tenant_id = :t AND f.expediente_id = :e AND f.embedding_model = :m "
                "ORDER BY f.embedding <=> CAST(:v AS vector) LIMIT 20"
            ),
            {"t": t_g, "e": e_g, "m": MODELO, "v": str(aleatorio())},
        )
        print("\nPlan de la rama vectorial en el expediente gigante:")
        for linea in plan.scalars():
            if "Sort Key" in linea:
                linea = "Sort Key: (embedding <=> <vector de consulta>)"
            print("   ", linea[:150])
    await engine.dispose()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--admin-url", required=True, help="postgresql://usuario:clave@host:puerto/postgres"
    )
    p.add_argument(
        "--fragmentos", type=int, default=100_000, help="fragmentos del resto de tenants"
    )
    p.add_argument("--gigante", type=int, default=40_000, help="fragmentos del expediente gigante")
    p.add_argument("--tenants", type=int, default=50)
    p.add_argument("--repeticiones", type=int, default=40)
    p.add_argument("--concurrencia", type=int, default=10)
    p.add_argument("--conservar", action="store_true", help="no borrar la base al terminar")
    a = p.parse_args()

    nombre = f"bench_{uuid.uuid4().hex[:8]}"
    print(f"Base desechable: {nombre}")
    url = preparar_base(a.admin_url, nombre)
    try:
        ids = cargar(url, a.fragmentos, a.tenants, a.gigante)
        asyncio.run(medir(url, ids, a.repeticiones, a.concurrencia))
    finally:
        if not a.conservar:
            with psycopg.connect(a.admin_url, autocommit=True) as c:
                c.execute(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)')
            print(f"\nBase {nombre} eliminada")


if __name__ == "__main__":
    main()
