"""«Preparar mi cita» contra el stack REAL (Gemini real): dos laboratorios y una fórmula inventados.

Igual que recorrido_cronologia_real.py (cuenta @example.com marcada como verificada en la base local), pero
pide la preparación de la cita y revisa que las preguntas no afirmen, receten ni dosifiquen. ELIMINA la
cuenta al final (o la conserva con `--conservar RUTA`). Uso, desde agente/:

    PYTHONPATH=. uv run python scripts/recorrido_preparacion_real.py [--conservar RUTA]
"""

import json
import sys
import time
import uuid

import httpx

from scripts.recorrido_cronologia_real import (
    API,
    CLAVE,
    LAB_MARZO,
    LAB_SEPTIEMBRE,
    verificar_en_base,
)
from tests.pdfs import pdf_texto

FORMULA = (
    "FORMULA MEDICA\n\nPaciente: Carlos Ruiz Mejia   CC 79.123.456\n\nFecha: 15/09/2025\n\n"
    "Diagnostico: dislipidemia.\n\nAtorvastatina 20 mg, una tableta en la noche.\n\nControl en 3 meses."
)
CONSERVAR = sys.argv[sys.argv.index("--conservar") + 1] if "--conservar" in sys.argv else None


def main() -> int:
    c = httpx.Client(timeout=300)
    email = f"preparacion-{uuid.uuid4().hex[:8]}@example.com"
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
                "codigo_expediente": "P",
                "titulo": "Mis documentos",
                "entidad_contratante": "Personal",
                "tipo_expediente": "AUDITORIA_CLINICA",
            },
        ).json()["id"]
        for nombre, texto in (
            ("lab_marzo.pdf", LAB_MARZO),
            ("lab_septiembre.pdf", LAB_SEPTIEMBRE),
            ("formula.pdf", FORMULA),
        ):
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
        x = c.post(f"{API}/expedientes/{e}/preparacion", headers=h)
        print("\npreparación:", x.status_code, f"{time.time() - t0:.1f}s")
        j = x.json()
        print(
            json.dumps(
                {
                    k: j.get(k)
                    for k in (
                        "eventos",
                        "cambios",
                        "medicamentos",
                        "diagnosticos",
                        "alergias",
                        "preguntas",
                        "alertas",
                    )
                },
                ensure_ascii=False,
                indent=1,
            )
        )
        texto = json.dumps(j, ensure_ascii=False).lower()
        ok = (
            x.status_code == 200
            and j.get("preguntas")
            and all(q.startswith("¿") and q.endswith("?") for q in j["preguntas"])
            and any(
                m["nombre"].lower().startswith("atorvastatina") for m in j.get("medicamentos", [])
            )
            and not any(
                w in texto for w in ("usted tiene", "padece", "es preocupante", "está bien")
            )
        )
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
