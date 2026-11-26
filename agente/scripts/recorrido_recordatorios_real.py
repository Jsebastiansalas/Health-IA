"""Recordatorios contra el stack REAL (Gemini real): un laboratorio y una fórmula inventados con controles.

Cuenta @example.com marcada como verificada en la base local (como recorrido_cronologia_real.py). Busca
controles, confirma uno, descarga su .ics y ELIMINA la cuenta (o la conserva con `--conservar RUTA`).
Las fechas propuestas quedan en 2025, así que el aviso diario por correo no las toca. Uso, desde agente/:

    PYTHONPATH=. uv run python scripts/recorrido_recordatorios_real.py [--conservar RUTA]
"""

import sys
import time
import uuid

import httpx

from scripts.recorrido_cronologia_real import API, CLAVE, LAB_SEPTIEMBRE, verificar_en_base
from scripts.recorrido_preparacion_real import FORMULA
from tests.pdfs import pdf_texto

CONSERVAR = sys.argv[sys.argv.index("--conservar") + 1] if "--conservar" in sys.argv else None


def main() -> int:
    c = httpx.Client(timeout=300)
    email = f"recordatorios-{uuid.uuid4().hex[:8]}@example.com"
    r = c.post(
        f"{API}/auth/registro-personal",
        json={"nombre": "Carlos Prueba", "email": email, "password": CLAVE},
    )
    r.raise_for_status()
    h = {"Authorization": f"Bearer {r.json().get('access_token') or r.json()['accessToken']}"}
    try:
        verificar_en_base(email)
        c.post(f"{API}/consentimiento", headers=h).raise_for_status()
        e = c.post(
            f"{API}/expedientes",
            headers=h,
            json={
                "codigo_expediente": "R",
                "titulo": "Mis documentos",
                "entidad_contratante": "Personal",
                "tipo_expediente": "AUDITORIA_CLINICA",
            },
        ).json()["id"]
        for nombre, texto in (("lab_septiembre.pdf", LAB_SEPTIEMBRE), ("formula.pdf", FORMULA)):
            doc = c.post(
                f"{API}/expedientes/{e}/documentos",
                headers=h,
                data={"tipo_documento": "HISTORIA_CLINICA", "numero_adenda": "0"},
                files={"archivo": (nombre, pdf_texto([texto]), "application/pdf")},
            ).json()["id"]
            for _ in range(90):
                d = c.get(f"{API}/expedientes/{e}/documentos/{doc}", headers=h).json()
                if d["estado_indexacion"].startswith(("INDEXADO", "ERROR")):
                    break
                time.sleep(2)
            print(nombre, "->", d["estado_indexacion"])

        t0 = time.time()
        x = c.post(f"{API}/expedientes/{e}/recordatorios/propuestas", headers=h)
        print("\npropuestas:", x.status_code, f"{time.time() - t0:.1f}s")
        lista = x.json()
        for p in lista:
            print(
                f"  [{p['estado']}] {p['texto']!r}  propuesta={p['fecha_propuesta']}  doc={p['fecha_documento']}  fuente={p['cita'].get('nombreArchivo')}"
            )
        segunda = c.post(f"{API}/expedientes/{e}/recordatorios/propuestas", headers=h).json()
        print("segunda búsqueda, sin repetir:", len(segunda) == len(lista))

        ok = x.status_code == 200 and lista and len(segunda) == len(lista)
        con_fecha = next((p for p in lista if p["fecha_propuesta"]), None)
        if con_fecha:
            conf = c.patch(
                f"{API}/recordatorios/{con_fecha['id']}", headers=h, json={"estado": "CONFIRMADO"}
            )
            ics = c.get(f"{API}/recordatorios/{con_fecha['id']}/calendario.ics", headers=h)
            print(
                "confirmar:", conf.status_code, conf.json().get("fecha"), "| ics:", ics.status_code
            )
            print(ics.text)
            ok = (
                ok
                and conf.status_code == 200
                and ics.status_code == 200
                and "Control médico" in ics.text
            )
            ok = (
                ok and con_fecha["texto"] not in ics.text
            )  # el calendario no lleva el texto del documento
        print("\nRESULTADO:", "OK" if ok else "REVISAR")
        return 0 if ok else 1
    finally:
        if CONSERVAR:
            with open(CONSERVAR, "w", encoding="utf-8") as f:
                f.write(f"{email}\n{CLAVE}\n")
            print("cuenta conservada:", CONSERVAR)
        else:
            print(
                "eliminar cuenta:",
                c.post(f"{API}/cuenta/eliminar", headers=h, json={"password": CLAVE}).status_code,
            )


if __name__ == "__main__":
    sys.exit(main())
