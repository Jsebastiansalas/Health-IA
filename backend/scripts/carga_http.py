"""Prueba de carga HTTP: ¿un login (bcrypt) frena a las demás peticiones?

Mide la latencia de una petición ligera (GET /api/v1/expedientes) en dos situaciones:
  A. sin carga;
  B. mientras otros clientes inician sesión en masa.
Si el hash de la contraseña bloqueara el bucle de eventos, B sería varias veces peor que A.

    uv run python scripts/carga_http.py --base http://localhost:8010 \
        --email admin@demo.co --password ClaveSegura123 --logins 40 --ligeras 150
Con límites de peticiones activos habrá respuestas 429: para medir capacidad bruta, arranque la API
con RATE_LIMIT_HABILITADO=false.
"""

import argparse
import asyncio
import statistics
import time

import httpx


def pct(datos: list[float], p: float) -> float:
    datos = sorted(datos)
    return datos[min(len(datos) - 1, int(len(datos) * p))]


async def main(a: argparse.Namespace) -> None:
    api = f"{a.base}/api/v1"
    limites = httpx.Limits(max_connections=200)
    async with httpx.AsyncClient(timeout=120, limits=limites) as c:
        r = await c.post(f"{api}/auth/login", json={"email": a.email, "password": a.password})
        r.raise_for_status()
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}

        async def ligera() -> float:
            t0 = time.perf_counter()
            x = await c.get(f"{api}/expedientes?limit=5", headers=h)
            assert x.status_code == 200, x.status_code
            return (time.perf_counter() - t0) * 1000

        async def login() -> tuple[float, int]:
            t0 = time.perf_counter()
            x = await c.post(f"{api}/auth/login", json={"email": a.email, "password": a.password})
            return (time.perf_counter() - t0) * 1000, x.status_code

        async def ligeras(n: int) -> list[float]:
            out = []
            for _ in range(n):
                out.append(await ligera())
                await asyncio.sleep(0.005)
            return out

        await ligeras(10)  # calentamiento
        base = await ligeras(a.ligeras)
        print(
            f"A. Sin carga:  p50={statistics.median(base):6.1f} ms  p95={pct(base, 0.95):6.1f} ms  "
            f"máx={max(base):6.1f} ms"
        )

        t0 = time.perf_counter()
        logins = asyncio.gather(*[login() for _ in range(a.logins)])
        bajo_carga = await ligeras(a.ligeras)
        resultados = await logins
        dur = time.perf_counter() - t0
        codigos = {}
        for _, cod in resultados:
            codigos[cod] = codigos.get(cod, 0) + 1
        print(
            f"B. Con {a.logins} logins simultáneos: p50={statistics.median(bajo_carga):6.1f} ms  "
            f"p95={pct(bajo_carga, 0.95):6.1f} ms  máx={max(bajo_carga):6.1f} ms"
        )
        tl = [t for t, cod in resultados if cod == 200]
        if tl:
            print(
                f"   logins: {len(tl) / dur:.1f}/s  p50={statistics.median(tl):.0f} ms  "
                f"p95={pct(tl, 0.95):.0f} ms  códigos={codigos}"
            )
        else:
            print(f"   ningún login 200: {codigos} (¿límites activos?)")
        print(
            f"   degradación de la petición ligera: x{statistics.median(bajo_carga) / statistics.median(base):.1f} "
            f"en p50, x{pct(bajo_carga, 0.95) / pct(base, 0.95):.1f} en p95"
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:8010")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--logins", type=int, default=40)
    p.add_argument("--ligeras", type=int, default=150)
    asyncio.run(main(p.parse_args()))
