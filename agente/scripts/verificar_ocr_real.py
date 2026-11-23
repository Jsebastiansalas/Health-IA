"""Prueba del OCR REAL (Tesseract) con fotos sintéticas de un documento, en distintas condiciones.

Se ejecuta DENTRO del contenedor del agente (allí está Tesseract con datos en español):

    docker cp agente/scripts/verificar_ocr_real.py medtender-agente-1:/tmp/ocr.py
    docker exec -e PYTHONPATH=/app medtender-agente-1 python /tmp/ocr.py

Por cada condición dice si la foto se acepta o se rechaza, con qué confianza y qué fracción de las
palabras del original recuperó. Sirve para calibrar `imagen_confianza_minima` e `imagen_texto_minimo`.
"""

import io
import re
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.pipeline.extraccion import ImagenNoLegible, extraer_imagen
from app.pipeline.modelos import ConfigExtraccion

TEXTO = [
    "LABORATORIO CLINICO SAN RAFAEL",
    "Paciente: Maria Gomez Rojas   Fecha: 12/11/2026",
    "Hemoglobina 13,2 g/dL   (ref 12,0 - 15,5)",
    "Glucosa en ayunas 92 mg/dL   (ref 70 - 100)",
    "Colesterol LDL 160 mg/dL   (ref < 130)  ALTO",
    "Creatinina 0,8 mg/dL",
    "Observaciones: control con medicina interna en un mes.",
]


def documento(ancho: int = 1600, tam: int = 38) -> Image.Image:
    img = Image.new("RGB", (ancho, 700), (250, 250, 247))
    d = ImageDraw.Draw(img)
    fuente = ImageFont.load_default(size=tam)
    y = 40
    for linea in TEXTO:
        d.text((50, y), linea, fill=(20, 20, 20), font=fuente)
        y += tam + 40
    return img


def con_sombra(img: Image.Image) -> Image.Image:
    sombra = Image.new("L", img.size, 255)
    d = ImageDraw.Draw(sombra)
    for x in range(img.width):
        d.line([(x, 0), (x, img.height)], fill=int(255 - 120 * x / img.width))
    return Image.composite(img, Image.new("RGB", img.size, (0, 0, 0)), sombra)


def jpg_con_exif_girado(img: Image.Image) -> bytes:
    """Como las fotos de móvil: píxeles girados y etiqueta EXIF que dice cómo enderezarlos."""
    girada = img.rotate(90, expand=True)  # los píxeles quedan de lado
    exif = Image.Exif()
    exif[0x0112] = 8  # al abrir, rotar 90° para enderezar
    b = io.BytesIO()
    girada.save(b, "JPEG", exif=exif, quality=88)
    return b.getvalue()


def heic(img: Image.Image) -> bytes:
    import pillow_heif

    pillow_heif.register_heif_opener()
    b = io.BytesIO()
    img.save(b, "HEIF", quality=80)
    return b.getvalue()


def png(img: Image.Image) -> bytes:
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def jpg(img: Image.Image, q: int = 85) -> bytes:
    b = io.BytesIO()
    img.save(b, "JPEG", quality=q)
    return b.getvalue()


base = documento()
degradado = Image.linear_gradient("L").resize((1600, 700)).convert("RGB")  # sin texto
CASOS = {
    "nítida (PNG)": (".png", png(base)),
    "nítida (JPG)": (".jpg", jpg(base)),
    "HEIC": (".heic", heic(base)),
    "EXIF girado (móvil)": (".jpg", jpg_con_exif_girado(base)),
    "ligeramente borrosa": (".jpg", jpg(base.filter(ImageFilter.GaussianBlur(1.5)))),
    "muy borrosa": (".jpg", jpg(base.filter(ImageFilter.GaussianBlur(5)))),
    "con sombra": (".jpg", jpg(con_sombra(base))),
    "baja resolución (500 px)": (".jpg", jpg(base.resize((500, 219)))),
    "JPG muy comprimido": (".jpg", jpg(base, 12)),
    "sin texto (radiografía)": (".jpg", jpg(degradado)),
}
ESPERADO = {
    "nítida (PNG)": "acepta", "nítida (JPG)": "acepta", "HEIC": "acepta", "EXIF girado (móvil)": "acepta",
    "ligeramente borrosa": "acepta", "muy borrosa": "rechaza", "con sombra": "acepta",
    "baja resolución (500 px)": "?", "JPG muy comprimido": "?", "sin texto (radiografía)": "rechaza",
}


def palabras(t: str) -> set[str]:
    return {w for w in re.findall(r"\w+", t.lower()) if len(w) > 3}


def main() -> int:
    cfg = ConfigExtraccion()
    originales = palabras(" ".join(TEXTO))
    print(f"umbral de confianza={cfg.imagen_confianza_minima}  texto mínimo={cfg.imagen_texto_minimo}\n")
    problemas = 0
    for nombre, (ext, datos) in CASOS.items():
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / f"foto{ext}"
            ruta.write_bytes(datos)
            try:
                r = extraer_imagen(str(ruta), cfg)
                p = r.paginas[0]
                texto = " ".join(parte.texto for parte in p.partes)
                rec = len(palabras(texto) & originales) / len(originales)
                resultado, detalle = "acepta", f"confianza {p.ocr_confidence:.0%}, palabras recuperadas {rec:.0%}"
            except ImagenNoLegible as exc:
                resultado, detalle = "rechaza", str(exc)[:90]
        esperado = ESPERADO[nombre]
        marca = "" if esperado in ("?", resultado) else "   <-- INESPERADO"
        problemas += bool(marca)
        print(f"{nombre:28} {resultado:8} {detalle}{marca}")
    print(f"\n{problemas} resultado(s) inesperado(s)")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
