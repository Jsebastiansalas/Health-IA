"""Registro de cambios a partir de los commits («tipo: emoji mensaje») y de las etiquetas vX.Y.Z.

    python infra/scripts/changelog.py                    # CHANGELOG.md con lo no publicado arriba
    python infra/scripts/changelog.py --version v0.43.0  # pone ese nombre a lo no publicado
    python infra/scripts/changelog.py --siguiente        # qué versión tocaría

No crea etiquetas: publicar es una decisión del dueño (ver README, «Versiones»).
"""

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SECCIONES = {"feat": "Novedades", "fix": "Correcciones", "perf": "Rendimiento", "docs": "Documentación"}
_MENSAJE = re.compile(r"^(?P<tipo>[a-z]+)(?:\([^)]*\))?!?:\s*(?P<texto>.+)$")
_EMOJI = re.compile(r"^[^\w¿¡«(\"']+")


def seccion(nombre: str, fecha: str, mensajes: list[str]) -> str:
    por_tipo: dict[str, list[str]] = {}
    for m in mensajes:
        r = _MENSAJE.match(m.strip())
        if r and r["tipo"] in SECCIONES:
            por_tipo.setdefault(r["tipo"], []).append(_EMOJI.sub("", r["texto"]))
    if not por_tipo:
        return ""
    bloques = [
        f"### {titulo}\n" + "".join(f"- {x}\n" for x in por_tipo[tipo])
        for tipo, titulo in SECCIONES.items()
        if tipo in por_tipo
    ]
    return f"## {nombre} ({fecha})\n\n" + "\n".join(bloques)


def siguiente(ultima: str | None, mensajes: list[str]) -> str:
    mayor, menor, parche = (int(x) for x in (ultima or "v0.0.0").lstrip("v").split("."))
    if any(m.startswith("feat") for m in mensajes) or ultima is None:
        return f"v{mayor}.{menor + 1}.0"
    return f"v{mayor}.{menor}.{parche + 1}"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout.strip()


def _mensajes(rango: str) -> list[str]:
    return [m for m in _git("log", "--no-merges", "--format=%s", rango).splitlines() if m]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--version", help="nombre para lo que aún no está publicado")
    p.add_argument("--siguiente", action="store_true")
    args = p.parse_args()

    etiquetas = _git("tag", "--list", "v*.*.*", "--merged", "HEAD", "--sort=-v:refname").split()
    ultima = etiquetas[0] if etiquetas else None
    pendientes = _mensajes(f"{ultima}..HEAD" if ultima else "HEAD")
    if args.siguiente:
        print(siguiente(ultima, pendientes))
        return 0

    partes = [seccion(args.version or "Sin publicar", date.today().isoformat(), pendientes)]
    for i, etiqueta in enumerate(etiquetas):
        anterior = etiquetas[i + 1] if i + 1 < len(etiquetas) else None
        rango = f"{anterior}..{etiqueta}" if anterior else etiqueta
        partes.append(seccion(etiqueta, _git("log", "-1", "--format=%as", etiqueta), _mensajes(rango)))
    cuerpo = "\n".join(x for x in partes if x)
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    print("# Registro de cambios\n\nGenerado con `python infra/scripts/changelog.py`.\n\n" + cuerpo, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
