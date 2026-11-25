"""Comprueba las redes y los puertos del despliegue de producción. No levanta nada.

Una red `internal: true` no tiene salida a internet: un servicio que deba llamar fuera y solo esté
en ella arranca bien y falla en silencio al usarse. Y al revés: nada que guarde datos debe salir ni
publicar puertos.

Uso, desde la raíz (necesita Docker):  python infra/scripts/comprobar_compose.py
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARCHIVOS = ["infra/docker-compose.prod.yml", "infra/docker-compose.monitoreo.yml"]

# Servicio -> por qué tiene que llegar a internet.
NECESITAN_INTERNET = {
    "api": "correo SMTP y contraseñas filtradas",
    "agente": "proveedor de IA",
    "worker": "proveedor de IA (embeddings)",
    "backup": "copia fuera del equipo",
    "caddy": "certificados",
    "clamav": "firmas del antivirus",
    "alertmanager": "correo de las alertas",
    "blackbox": "revisar el certificado del dominio",
}
SOLO_INTERNOS = {"postgres", "redis", "prometheus", "estado-respaldos"}
# Únicos puertos que se pueden publicar. Grafana solo en la propia máquina.
PUEDEN_PUBLICAR = {"caddy", "grafana"}


def configuracion() -> dict:
    archivos = [a for a in ARCHIVOS if (RAIZ / a).exists()]
    # Valores inventados para todo lo que el compose exige: solo se mira su forma.
    texto = "".join((RAIZ / a).read_text(encoding="utf-8") for a in archivos)
    entorno = dict(os.environ)
    for nombre in re.findall(r"\$\{([A-Z_]+):\?", texto):
        entorno[nombre] = "valor-inventado"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as falso:
        falso.write("{}")
    entorno["VERTEX_CREDENCIALES_ARCHIVO"] = falso.name
    orden = ["docker", "compose"]
    for a in archivos:
        orden += ["-f", str(RAIZ / a)]
    try:
        salida = subprocess.run(
            [*orden, "config", "--format", "json"],
            env=entorno, capture_output=True, text=True, encoding="utf-8", check=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        sys.exit(f"El compose no es válido:\n{exc.stderr}")
    finally:
        os.unlink(falso.name)
    return json.loads(salida)


def main() -> int:
    c = configuracion()
    sin_salida = {n for n, r in c.get("networks", {}).items() if (r or {}).get("internal")}
    fallos = []
    for nombre, servicio in c["services"].items():
        redes = set(servicio.get("networks") or {"default": None})
        sale = bool(redes - sin_salida)
        if nombre in NECESITAN_INTERNET and not sale:
            fallos.append(f"{nombre} no tiene salida a internet y la necesita: {NECESITAN_INTERNET[nombre]}")
        if nombre in SOLO_INTERNOS and sale:
            fallos.append(f"{nombre} guarda datos y tiene salida a internet")
        for puerto in servicio.get("ports") or []:
            if nombre not in PUEDEN_PUBLICAR:
                fallos.append(f"{nombre} publica el puerto {puerto.get('published')}")
            elif nombre == "grafana" and puerto.get("host_ip") != "127.0.0.1":
                fallos.append("grafana debe publicarse solo en 127.0.0.1")
    for f in fallos:
        print(f"FALLA  {f}")
    if not fallos:
        print(f"OK     redes y puertos correctos en {len(c['services'])} servicios")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
