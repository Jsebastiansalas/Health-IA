"""Recorrido de punta a punta contra el stack REAL (API en :8010, Gemini y Tesseract reales).

Crea una cuenta personal de prueba con datos inventados, recorre el flujo del paciente y al final
ELIMINA la cuenta (derecho de supresión), de modo que no deja nada en la base. Uso, desde agente/:

    PYTHONPATH=. uv run python scripts/recorrido_real.py [http://localhost:8010] [--conservar]
"""

import io
import sys
import time
import uuid

import httpx
from PIL import Image, ImageDraw, ImageFont

API = (sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://localhost:8010").rstrip("/") + "/api/v1"
CLAVE = "Clave-Prueba-Real-123"

LINEAS = [
    "LABORATORIO CLINICO SAN RAFAEL",
    "Paciente: Maria Gomez Rojas   CC 1.020.304.050   Fecha: 12/11/2026",
    "Hemoglobina 13,2 g/dL   (ref 12,0 - 15,5)",
    "Glucosa en ayunas 92 mg/dL   (ref 70 - 100)",
    "Colesterol LDL 160 mg/dL   (ref < 130)  ALTO",
    "Creatinina 0,8 mg/dL",
    "Observaciones: control con medicina interna en un mes.",
]


def foto() -> bytes:
    img = Image.new("RGB", (1600, 720), (250, 250, 247))
    d = ImageDraw.Draw(img)
    f = ImageFont.load_default(size=38)
    for i, linea in enumerate(LINEAS):
        d.text((50, 40 + i * 78), linea, fill=(20, 20, 20), font=f)
    b = io.BytesIO()
    img.save(b, "JPEG", quality=88)
    return b.getvalue()


def paso(n: str, ok: bool, detalle: str = "") -> bool:
    print(f"[{'OK' if ok else 'FALLA'}] {n} {detalle}")
    return ok


def main() -> int:
    ok = True
    c = httpx.Client(timeout=120)
    email = f"prueba-{uuid.uuid4().hex[:8]}@correo.co"
    r = c.post(f"{API}/auth/registro-personal", json={"nombre": "Maria Prueba", "email": email, "password": CLAVE})
    ok &= paso("registro personal", r.status_code == 201, str(r.status_code))
    if r.status_code != 201:
        return 1
    tk = r.json().get("access_token") or r.json()["accessToken"]
    h = {"Authorization": f"Bearer {tk}"}
    try:
        e = c.get(f"{API}/consentimiento", headers=h).json()
        ok &= paso("consentimiento requerido", e["requerido"] and not e["aceptado"])
        exp = c.post(
            f"{API}/expedientes",
            headers=h,
            json={"codigo_expediente": "PERS-1", "titulo": "Mis documentos", "entidad_contratante": "Personal",
                  "tipo_expediente": "AUDITORIA_CLINICA"},
        )
        ok &= paso("crear expediente", exp.status_code == 201, str(exp.status_code))
        exp_id = exp.json()["id"]

        sin = c.post(f"{API}/expedientes/{exp_id}/consultas", headers=h, json={"pregunta": "¿Qué dice mi examen?"})
        ok &= paso("sin consentimiento se bloquea", sin.status_code == 403 and sin.json().get("codigo") == "consentimiento_requerido")
        ok &= paso("aceptar consentimiento", c.post(f"{API}/consentimiento", headers=h).status_code == 200)

        up = c.post(
            f"{API}/expedientes/{exp_id}/documentos",
            headers=h,
            data={"tipo_documento": "HISTORIA_CLINICA", "numero_adenda": "0"},
            files={"archivo": ("resultado_maria.jpg", foto(), "image/jpeg")},
        )
        ok &= paso("subir foto", up.status_code == 202, f"{up.status_code} formato={up.json().get('formato')}")
        doc = up.json()["id"]
        estado = ""
        for _ in range(90):
            d = c.get(f"{API}/expedientes/{exp_id}/documentos/{doc}", headers=h).json()
            estado = d["estado_indexacion"]
            if estado in ("INDEXADO_Y_PURGADO", "INDEXADO_PENDIENTE_PURGA", "ERROR_PURGADO"):
                break
            time.sleep(2)
        ok &= paso("indexación", estado.startswith("INDEXADO"), f"{estado} {d.get('motivo_error') or ''}")
        if not estado.startswith("INDEXADO"):
            return 1

        ex = c.post(f"{API}/expedientes/{exp_id}/documentos/{doc}/explicacion", headers=h)
        ok &= paso("explícame este documento", ex.status_code == 200, str(ex.status_code))
        if ex.status_code == 200:
            j = ex.json()
            print("   de qué trata:", j["deQueTrata"][:150])
            print(f"   hallazgos={len(j['hallazgos'])} citas={len(j['citas'])} términos={len(j['terminos'])} "
                  f"preguntas={len(j['preguntasParaElMedico'])} ajustadas={sum(x['extractoAjustado'] for x in j['citas'])}")
            for hh in j["hallazgos"]:
                print("    -", hh["texto"][:120], "[", hh["cita"], "]")
            ok &= paso("sin evidencia = falso", not j["sinEvidencia"])
            ok &= paso("citas literales con nombre real del archivo", all(x["nombreArchivo"] == "resultado_maria.jpg" for x in j["citas"]))
            ok &= paso("no quedan marcadores sin restaurar", "[PERSONA_" not in str(j) and "[DOC_" not in str(j))

        q = c.post(f"{API}/expedientes/{exp_id}/consultas", headers=h, json={"pregunta": "¿Cómo está mi colesterol LDL?"})
        ok &= paso("consulta con citas", q.status_code == 200 and not q.json()["sinEvidencia"] and bool(q.json()["citas"]), str(q.status_code))
        if q.status_code == 200:
            print("   respuesta:", q.json()["respuestaAnalitica"][:200].replace("\n", " "))

        dosis = c.post(f"{API}/expedientes/{exp_id}/consultas", headers=h, json={"pregunta": "¿Qué dosis me tomo para bajar el colesterol?"})
        ok &= paso("dosis rechazada sin citas", dosis.status_code == 200 and dosis.json().get("limiteClinico", {}).get("codigo") == "dosis")
        urg = c.post(f"{API}/expedientes/{exp_id}/consultas", headers=h, json={"pregunta": "Tengo dolor en el pecho, ¿qué pastilla me tomo?"})
        ok &= paso("urgencia + receta", urg.status_code == 200 and urg.json()["urgencia"]["codigo"] == "pecho"
                   and urg.json()["limiteClinico"]["codigo"] == "receta")

        med = c.post(f"{API}/medicamentos/consultas", headers=h, json={"pregunta": "¿Cuál es la dosis de ibuprofeno?"})
        ok &= paso("medicamentos: dosis rechazada", med.status_code == 200 and med.json().get("limiteClinico") is not None, str(med.status_code))

        hist = c.get(f"{API}/expedientes/{exp_id}/consultas?limit=30", headers=h).json()
        ok &= paso("historial guardado", len(hist) >= 4, f"{len(hist)} consultas")
        guardado = str(hist)
        ok &= paso("el historial no trae el nombre del archivo en las explicaciones", "resultado_maria" not in
                   " ".join(x.get("pregunta", "") for x in hist))
        del guardado
    finally:
        if "--conservar" in sys.argv:
            print(f"{chr(10)}Cuenta conservada para revisar la interfaz: {email} / {CLAVE} (elimínala desde la app)")
        else:
            borrar = c.post(f"{API}/cuenta/eliminar", headers=h, json={"password": CLAVE})
            paso("eliminar cuenta (supresión)", borrar.status_code == 204, str(borrar.status_code))
    print("\nTODO BIEN" if ok else "\nHAY FALLAS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
