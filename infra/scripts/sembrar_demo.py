"""Crea una organización de demostración con un usuario por rol en la API de DESARROLLO.

    python infra/scripts/sembrar_demo.py [--api http://localhost:8010]

Todos los usuarios de demostración comparten la contraseña fija CLAVE_DEMO (más abajo). Es SOLO para
desarrollo local: nunca la use contra producción (allí el registro público debe estar cerrado).
Es idempotente: si la organización ya existe, solo comprueba que los usuarios puedan iniciar sesión.
Requiere httpx.
"""

import argparse
import sys
from urllib.parse import urlparse

import httpx

# Contraseña de demostración, fija y conocida (solo desarrollo local).
CLAVE_DEMO = "Demo-Medtender-2027"
DOMINIO = "demo-hospital.co"
USUARIOS = [
    ("admin", "ADMIN_TENANT", "Administradora Demo"),
    ("juridico", "JURIDICO", "Abogado Demo"),
    ("auditor", "AUDITOR_MEDICO", "Auditora Médica Demo"),
    ("biomedico", "BIOMEDICO", "Ingeniero Biomédico Demo"),
    ("lector", "LECTOR", "Lector Demo"),
]


def _es_local(api: str) -> bool:
    host = urlparse(api).hostname or ""
    return host in ("localhost", "127.0.0.1", "::1") or host.endswith((".localhost", ".test"))


def main(api: str) -> None:
    # La contraseña de demostración es pública: jamás debe crearse en un servidor real.
    if not _es_local(api):
        sys.exit(f"Rechazado: {api} no es un entorno local. Esta contraseña es pública; solo para desarrollo.")
    base = f"{api}/api/v1"
    with httpx.Client(timeout=30) as c:
        admin = f"admin@{DOMINIO}"
        r = c.post(
            f"{base}/auth/registro-tenant",
            json={
                "tenant_nombre": "Hospital Demo",
                "nit": "DEMO-900001",
                "admin_email": admin,
                "admin_password": CLAVE_DEMO,
                "admin_nombre": USUARIOS[0][2],
            },
        )
        if r.status_code == 201:
            cab = {"Authorization": f"Bearer {r.json()['access_token']}"}
            for usuario, rol, nombre in USUARIOS[1:]:
                x = c.post(
                    f"{base}/usuarios",
                    headers=cab,
                    json={
                        "email": f"{usuario}@{DOMINIO}",
                        "password": CLAVE_DEMO,
                        "nombre_completo": nombre,
                        "rol_global": rol,
                    },
                )
                x.raise_for_status()
        elif r.status_code != 409:  # 409: la organización de demostración ya existe
            r.raise_for_status()
        for usuario, rol, _ in USUARIOS:
            email = f"{usuario}@{DOMINIO}"
            ok = c.post(f"{base}/auth/login", json={"email": email, "password": CLAVE_DEMO}).status_code == 200
            print(f"{'OK   ' if ok else 'FALLA'} {email:<28} {rol}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--api", default="http://localhost:8010")
    main(p.parse_args().api)
