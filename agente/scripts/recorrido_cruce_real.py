"""Cruce medicamentos ↔ fichas contra el stack REAL (Gemini real, fichas CIMA reales ya cargadas).

Antes: `docker exec medtender-agente-1 python -m app.cli cargar-fichas ibuprofeno` (verifica la licencia
de CIMA antes de usar esto fuera de pruebas). Crea una cuenta personal con un documento inventado
(fórmula de ibuprofeno, diagnóstico de úlcera gástrica y alergia a la penicilina), pide el cruce y
ELIMINA la cuenta. Uso, desde agente/:

    PYTHONPATH=. uv run python scripts/recorrido_cruce_real.py [http://localhost:8010]
"""

import io
import sys
import time
import uuid

import httpx
from PIL import Image, ImageDraw, ImageFont

API = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8010").rstrip("/") + "/api/v1"
CLAVE = "Clave-Prueba-Real-123"
LINEAS = [
    "HISTORIA CLINICA",
    "Paciente: Carlos Ruiz Mejia   CC 79.123.456",
    "Diagnostico: ulcera gastrica.",
    "Alergia: penicilina.",
    "Formula: Ibuprofeno 400 mg. Control en un mes.",
]


def foto() -> bytes:
    img = Image.new("RGB", (1600, 520), (250, 250, 247))
    d = ImageDraw.Draw(img)
    f = ImageFont.load_default(size=40)
    for i, linea in enumerate(LINEAS):
        d.text((50, 40 + i * 85), linea, fill=(20, 20, 20), font=f)
    b = io.BytesIO()
    img.save(b, "JPEG", quality=90)
    return b.getvalue()


def main() -> int:
    c = httpx.Client(timeout=180)
    email = f"cruce-{uuid.uuid4().hex[:8]}@correo.co"
    r = c.post(f"{API}/auth/registro-personal", json={"nombre": "Carlos Prueba", "email": email, "password": CLAVE})
    tk = r.json().get("access_token") or r.json()["accessToken"]
    h = {"Authorization": f"Bearer {tk}"}
    try:
        c.post(f"{API}/consentimiento", headers=h)
        e = c.post(f"{API}/expedientes", headers=h, json={"codigo_expediente": "C", "titulo": "Mis documentos",
                   "entidad_contratante": "Personal", "tipo_expediente": "AUDITORIA_CLINICA"}).json()["id"]
        up = c.post(f"{API}/expedientes/{e}/documentos", headers=h, data={"tipo_documento": "HISTORIA_CLINICA", "numero_adenda": "0"},
                    files={"archivo": ("formula.jpg", foto(), "image/jpeg")})
        doc = up.json()["id"]
        for _ in range(90):
            d = c.get(f"{API}/expedientes/{e}/documentos/{doc}", headers=h).json()
            if d["estado_indexacion"].startswith("INDEXADO") or d["estado_indexacion"] == "ERROR_PURGADO":
                break
            time.sleep(2)
        print("indexación:", d["estado_indexacion"], d.get("motivo_error") or "")
        x = c.post(f"{API}/expedientes/{e}/medicamentos/cruce", headers=h)
        print("cruce:", x.status_code)
        j = x.json()
        print("medicamentos:", [(m["nombre"], m.get("ficha")) for m in j["medicamentos"]])
        print("diagnósticos:", [d["texto"] for d in j["diagnosticos"]], "alergias:", [a["texto"] for a in j["alergias"]])
        for a in j["advertencias"]:
            print(f"  - {a['medicamento']} <-> {a['dato']}: {a['texto']}  [citas {a['citaMedicamento']},{a['citaDato']} ficha {a['ficha']}]")
        print("fichas citadas:", [(f['seccion'], f['titulo'], f['medicamento']) for f in j["fichas"]])
        print("alertas:", j["alertas"])
        ok = x.status_code == 200 and j["medicamentos"] and not any(
            w in (a["texto"].lower()) for a in j["advertencias"] for w in ("deja de", "debes tomar", "puedes tomar", "no tomes")
        )
        print("\nRESULTADO:", "OK" if ok else "REVISAR")
        return 0 if ok else 1
    finally:
        print("eliminar cuenta:", c.post(f"{API}/cuenta/eliminar", headers=h, json={"password": CLAVE}).status_code)


if __name__ == "__main__":
    sys.exit(main())
