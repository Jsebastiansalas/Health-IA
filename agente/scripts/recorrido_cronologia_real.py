"""Línea de tiempo contra el stack REAL (Gemini real, indexación real) con dos laboratorios inventados.

Crea una cuenta personal de prueba (correo @example.com, dominio reservado que no llega a nadie), la marca como
verificada directamente en la base local, sube dos resultados de laboratorio en fechas distintas, pide la línea
de tiempo dos veces (la segunda debe volver guardada, sin llamar al modelo) y ELIMINA la cuenta. Uso, desde agente/:

    PYTHONPATH=. uv run python scripts/recorrido_cronologia_real.py [http://localhost:8010] [--conservar RUTA]

Con `--conservar RUTA` no elimina la cuenta: escribe su correo y clave en RUTA (fuera del repositorio) para
revisar la pantalla; después hay que eliminarla desde el menú del usuario.
"""

import json
import subprocess
import sys
import time
import uuid

import httpx

from tests.pdfs import pdf_texto

_ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
CONSERVAR = sys.argv[sys.argv.index("--conservar") + 1] if "--conservar" in sys.argv else None
if CONSERVAR in _ARGS:
    _ARGS.remove(CONSERVAR)
API = (_ARGS[0] if _ARGS else "http://localhost:8010").rstrip("/") + "/api/v1"
CLAVE = "Clave-Prueba-Real-123"
POSTGRES = "medtender-postgres-1"

LAB_MARZO = (
    "LABORATORIO CLINICO SANTA ANA\n\nPaciente: Carlos Ruiz Mejia   CC 79.123.456\n\n"
    "Fecha de toma: 12/03/2025\n\n"
    "HEMOGRAMA\n\nHemoglobina 13,2 g/dL   Rango 12,0 - 15,5\n\nHematocrito 40 %   Rango 36 - 46\n\n"
    "PERFIL LIPIDICO\n\nColesterol LDL 160 mg/dL   ALTO   Valor de referencia < 130\n\n"
    "Glicemia en ayunas 98 mg/dL   Rango 70 - 100"
)
LAB_SEPTIEMBRE = (
    "LABORATORIO CLINICO SANTA ANA\n\nPaciente: Carlos Ruiz Mejia   CC 79.123.456\n\n"
    "Fecha de toma: 15 de septiembre de 2025\n\n"
    "Hb 12,1 g/dL   Rango 12,0 - 15,5\n\nColesterol LDL 128 mg/dL   Valor de referencia < 130\n\n"
    "Glucosa basal 104 mg/dL   ALTO   Rango 70 - 100\n\n"
    "Observaciones: control en 3 meses con medicina interna."
)


def verificar_en_base(email: str) -> None:
    sql = (
        "UPDATE verificaciones_correo v SET usado_at = now() FROM usuarios u "
        f"WHERE u.id = v.usuario_id AND u.email = '{email}';"
    )
    subprocess.run(
        ["docker", "exec", POSTGRES, "psql", "-U", "medtender", "-d", "medtender", "-c", sql],
        check=True,
        capture_output=True,
    )


def main() -> int:
    c = httpx.Client(timeout=300)
    email = f"cronologia-{uuid.uuid4().hex[:8]}@example.com"
    r = c.post(
        f"{API}/auth/registro-personal",
        json={"nombre": "Carlos Prueba", "email": email, "password": CLAVE},
    )
    r.raise_for_status()
    tk = r.json().get("access_token") or r.json()["accessToken"]
    h = {"Authorization": f"Bearer {tk}"}
    try:
        verificar_en_base(email)
        c.post(f"{API}/consentimiento", headers=h).raise_for_status()
        e = c.post(
            f"{API}/expedientes",
            headers=h,
            json={
                "codigo_expediente": "T",
                "titulo": "Mis documentos",
                "entidad_contratante": "Personal",
                "tipo_expediente": "AUDITORIA_CLINICA",
            },
        ).json()["id"]
        for nombre, texto in (("lab_marzo.pdf", LAB_MARZO), ("lab_septiembre.pdf", LAB_SEPTIEMBRE)):
            up = c.post(
                f"{API}/expedientes/{e}/documentos",
                headers=h,
                data={"tipo_documento": "HISTORIA_CLINICA", "numero_adenda": "0"},
                files={"archivo": (nombre, pdf_texto([texto]), "application/pdf")},
            )
            doc = up.json()["id"]
            for _ in range(90):
                d = c.get(f"{API}/expedientes/{e}/documentos/{doc}", headers=h).json()
                if d["estado_indexacion"].startswith("INDEXADO") or d[
                    "estado_indexacion"
                ].startswith("ERROR"):
                    break
                time.sleep(2)
            print(nombre, "->", d["estado_indexacion"])

        t0 = time.time()
        x = c.post(f"{API}/expedientes/{e}/cronologia", headers=h)
        print("\nlínea de tiempo:", x.status_code, f"{time.time() - t0:.1f}s")
        j = x.json()
        print(
            json.dumps(
                {k: j.get(k) for k in ("eventos", "alertas", "guardada")},
                ensure_ascii=False,
                indent=1,
            )
        )
        for a in j.get("analitos", []):
            print(f"  {a['nombre']} ({a['clave']}) comparable={a['comparable']}:")
            for v in a["valores"]:
                print(
                    f"     {v['fecha']}  {v['valorTexto']} {v['unidad'] or ''}  rango={v['rango']}  marca={v['marca']}  cita={v['cita']}"
                )
        t0 = time.time()
        y = c.post(f"{API}/expedientes/{e}/cronologia", headers=h).json()
        print("\nsegunda vez: guardada =", y.get("guardada"), f"{time.time() - t0:.1f}s")

        hb = next((a for a in j.get("analitos", []) if a["clave"] == "hemoglobina"), None)
        ok = (
            x.status_code == 200
            and hb is not None
            and [v["fecha"] for v in hb["valores"] if v["fecha"]] == ["2025-03-12", "2025-09-15"]
            and y.get("guardada") is True
            and not any(
                w in json.dumps(j, ensure_ascii=False).lower()
                for w in ("preocupante", "es normal", "está bien", "debe consultar urgente")
            )
        )
        print("\nRESULTADO:", "OK" if ok else "REVISAR")
        return 0 if ok else 1
    finally:
        if CONSERVAR:
            with open(CONSERVAR, "w", encoding="utf-8") as f:
                f.write(f"{email}\n{CLAVE}\n")
            print("cuenta conservada para revisar la pantalla:", CONSERVAR)
        else:
            print(
                "eliminar cuenta:",
                c.post(f"{API}/cuenta/eliminar", headers=h, json={"password": CLAVE}).status_code,
            )


if __name__ == "__main__":
    sys.exit(main())
