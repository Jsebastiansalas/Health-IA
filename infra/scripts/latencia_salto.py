"""¿Cuánto cuesta el salto Java -> agente Python?

Compara la misma petición hecha (A) directo al agente con el token interno y (B) a través de la
API Java con un usuario real (JWT, lectura del usuario en la base, autorización y proxy). Se usa
GET /embeddings/modelos porque no toca el LLM ni los embeddings: la diferencia es el costo puro
de la API Java. Opcionalmente mide una consulta RAG completa de punta a punta.

    python infra/scripts/latencia_salto.py --api http://localhost:8010 --agente http://localhost:8012 \
        --token-interno $INTERNAL_TOKEN --email admin@demo.co --password ClaveSegura123 \
        --expediente <uuid> --consultas 5

Con límites de peticiones activos habrá respuestas 429 (600/min por IP): arranque la API con
RATE_LIMIT_HABILITADO=false para medir. Solo requiere httpx.
"""

import argparse
import asyncio
import statistics
import time

import httpx


def pct(datos: list[float], p: float) -> float:
    datos = sorted(datos)
    return datos[min(len(datos) - 1, int(len(datos) * p))]


def resumen(nombre: str, ms: list[float]) -> None:
    print(
        f"{nombre:<34} p50={statistics.median(ms):7.1f} ms  p95={pct(ms, 0.95):7.1f} ms  "
        f"máx={max(ms):7.1f} ms  (n={len(ms)})"
    )


async def medir(c: httpx.AsyncClient, url: str, headers: dict, n: int) -> list[float]:
    salida = []
    for _ in range(n):
        t0 = time.perf_counter()
        r = await c.get(url, headers=headers)
        assert r.status_code == 200, (url, r.status_code, r.text[:200])
        salida.append((time.perf_counter() - t0) * 1000)
    return salida


async def main(a: argparse.Namespace) -> None:
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.post(
            f"{a.api}/api/v1/auth/login", json={"email": a.email, "password": a.password}
        )
        r.raise_for_status()
        usuario = {"Authorization": f"Bearer {r.json()['access_token']}"}
        interno = {"X-Internal-Token": a.token_interno}

        directo = f"{a.agente}/internal/v1/embeddings/modelos"
        via_java = f"{a.api}/api/v1/embeddings/modelos"
        await medir(c, directo, interno, 10)  # calentamiento
        await medir(c, via_java, usuario, 10)
        A = await medir(c, directo, interno, a.n)
        B = await medir(c, via_java, usuario, a.n)
        resumen("A. directo al agente", A)
        resumen("B. a través de la API Java", B)
        print(
            f"   costo del salto Java: +{statistics.median(B) - statistics.median(A):.1f} ms en p50, "
            f"+{pct(B, 0.95) - pct(A, 0.95):.1f} ms en p95"
        )

        if a.expediente:
            tiempos = []
            for i in range(a.consultas):
                t0 = time.perf_counter()
                x = await c.post(
                    f"{a.api}/api/v1/expedientes/{a.expediente}/consultas",
                    headers=usuario,
                    json={"pregunta": f"¿Cuál es la vigencia de las garantías? ({i})"},
                )
                assert x.status_code == 200, (x.status_code, x.text[:200])
                tiempos.append((time.perf_counter() - t0) * 1000)
                interna = x.json().get("latenciaMs", 0)
                print(f"   consulta {i + 1}: {tiempos[-1]:7.0f} ms de punta a punta ({interna} ms dentro del agente)")
            resumen("C. consulta RAG de punta a punta", tiempos)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--api", default="http://localhost:8010")
    p.add_argument("--agente", default="http://localhost:8012")
    p.add_argument("--token-interno", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--expediente", help="uuid de un expediente indexado (para medir una consulta real)")
    p.add_argument("--consultas", type=int, default=5)
    p.add_argument("-n", type=int, default=200)
    asyncio.run(main(p.parse_args()))
