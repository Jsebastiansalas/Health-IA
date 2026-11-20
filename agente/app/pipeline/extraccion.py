"""Extracción híbrida página a página (Paso 5).

- Texto nativo con pdfium. Si la página tiene tablas con líneas, se usa pdfplumber para
  intercalar texto y tablas Markdown en orden de lectura.
- OCR (Tesseract, 300 DPI) solo en páginas con casi nada de texto nativo y una imagen grande,
  es decir, páginas escaneadas. Se rasteriza únicamente esa página.
- Las imágenes incrustadas relevantes marcan has_visual_elements; las de tamaño de sello o
  firma, o las páginas con vocabulario de firma/sello, marcan has_signatures_or_stamps.

Todo es síncrono y se ejecuta en un proceso aparte (pdfium no es seguro entre hilos).
"""

import logging
import re
from dataclasses import dataclass

import pdfplumber
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from app.pipeline import tablas
from app.pipeline.modelos import (
    ConfigExtraccion,
    MetodoExtraccion,
    PaginaExtraida,
    Parte,
    ResultadoExtraccion,
)

log = logging.getLogger(__name__)

_VOCABULARIO_FIRMA = re.compile(
    r"\b(firma(do|da)?|sello|notar[ií]a|notario|autenticaci[oó]n|autenticad[oa]|"
    r"representante\s+legal|apostill[ae])\b",
    re.IGNORECASE,
)


# ---------- Decisiones puras (testeables sin PDF) ----------
@dataclass(frozen=True)
class Clasificacion:
    usar_ocr: bool
    has_visual_elements: bool
    posible_sello: bool


def clasificar_pagina(
    largo_texto_nativo: int, coberturas_imagen: list[float], cfg: ConfigExtraccion
) -> Clasificacion:
    """`coberturas_imagen`: fracción del área de la página que ocupa cada imagen."""
    relevantes = [c for c in coberturas_imagen if c >= cfg.imagen_relevante_min_area]
    escaneada = any(c >= cfg.imagen_escaneo_min_area for c in relevantes)
    return Clasificacion(
        usar_ocr=largo_texto_nativo < cfg.umbral_texto_nativo and escaneada,
        has_visual_elements=bool(relevantes),
        posible_sello=any(c <= cfg.imagen_sello_max_area for c in relevantes),
    )


def tiene_vocabulario_firma(texto: str) -> bool:
    return bool(_VOCABULARIO_FIRMA.search(texto))


# ---------- pdfium ----------
def _coberturas_imagen(pagina: pdfium.PdfPage) -> list[float]:
    ancho, alto = pagina.get_size()
    area = ancho * alto or 1.0
    coberturas = []
    for obj in pagina.get_objects(filter=(pdfium_c.FPDF_PAGEOBJ_IMAGE,)):
        izq, abajo, der, arriba = obj.get_bounds()
        # Recorta a la página: hay imágenes que sobresalen del área visible.
        w = max(0.0, min(der, ancho) - max(izq, 0.0))
        h = max(0.0, min(arriba, alto) - max(abajo, 0.0))
        coberturas.append((w * h) / area)
    return coberturas


def _texto_nativo(pagina: pdfium.PdfPage) -> str:
    textpage = pagina.get_textpage()
    try:
        return textpage.get_text_bounded().replace("\r\n", "\n").replace("\r", "\n")
    finally:
        textpage.close()


# ---------- pdfplumber: texto + tablas en orden de lectura ----------
def _partes_con_tablas(pagina_plumber) -> list[Parte] | None:
    """Devuelve None si la página no tiene tablas detectables."""
    encontradas = pagina_plumber.find_tables()
    if not encontradas:
        return None

    bloques: list[tuple[float, Parte]] = []
    bboxes = []
    for tabla in encontradas:
        md = tablas.a_markdown(tabla.extract())
        if md:
            bloques.append((tabla.bbox[1], Parte(md, es_tabla=True)))
            bboxes.append(tabla.bbox)
    if not bboxes:
        return None

    def fuera_de_tablas(obj) -> bool:
        cx = (obj["x0"] + obj["x1"]) / 2
        cy = (obj["top"] + obj["bottom"]) / 2
        return not any(x0 <= cx <= x1 and top <= cy <= bottom for x0, top, x1, bottom in bboxes)

    for linea in pagina_plumber.filter(fuera_de_tablas).extract_text_lines():
        texto = linea["text"].strip()
        if texto:
            bloques.append((linea["top"], Parte(texto)))

    bloques.sort(key=lambda b: b[0])
    # Las líneas de texto consecutivas se agrupan en un solo párrafo.
    partes: list[Parte] = []
    for _, parte in bloques:
        if partes and not parte.es_tabla and not partes[-1].es_tabla:
            partes[-1] = Parte(partes[-1].texto + "\n" + parte.texto)
        else:
            partes.append(parte)
    return partes


# ---------- OCR ----------
def _ocr(pagina: pdfium.PdfPage, cfg: ConfigExtraccion) -> tuple[str, float | None]:
    import pytesseract
    from pytesseract import Output

    imagen = pagina.render(scale=cfg.ocr_dpi / 72).to_pil()
    datos = pytesseract.image_to_data(imagen, lang=cfg.ocr_idioma, output_type=Output.DICT)

    lineas: list[str] = []
    confianzas: list[float] = []
    clave_actual = None
    palabras: list[str] = []
    parrafo_actual = None
    for i, palabra in enumerate(datos["text"]):
        palabra = palabra.strip()
        if not palabra:
            continue
        conf = float(datos["conf"][i])
        if conf >= 0:
            confianzas.append(conf)
        parrafo = (datos["block_num"][i], datos["par_num"][i])
        clave = (*parrafo, datos["line_num"][i])
        if clave != clave_actual:
            if palabras:
                lineas.append(" ".join(palabras))
            if parrafo_actual is not None and parrafo != parrafo_actual:
                lineas.append("")  # separa párrafos
            palabras, clave_actual, parrafo_actual = [], clave, parrafo
        palabras.append(palabra)
    if palabras:
        lineas.append(" ".join(palabras))

    confianza = round(sum(confianzas) / len(confianzas) / 100, 3) if confianzas else None
    return "\n".join(lineas).strip(), confianza


def version_tesseract() -> str:
    import pytesseract

    v = pytesseract.get_tesseract_version()
    return f"tesseract-{v.major}.{v.minor}-v1"


def tesseract_disponible() -> bool:
    try:
        version_tesseract()
        return True
    except Exception:
        return False


# ---------- Orquestación por página ----------
def _extraer_pagina(
    numero: int, pagina: pdfium.PdfPage, pagina_plumber, cfg: ConfigExtraccion
) -> PaginaExtraida:
    texto = _texto_nativo(pagina).strip()
    clasif = clasificar_pagina(len(texto), _coberturas_imagen(pagina), cfg)

    if clasif.usar_ocr:
        texto_ocr, confianza = _ocr(pagina, cfg)
        partes = [Parte(texto_ocr)] if texto_ocr else []
        resultado = PaginaExtraida(
            numero=numero,
            metodo=MetodoExtraccion.OCR,
            partes=partes,
            ocr_confidence=confianza,
        )
    else:
        partes_tabla = _partes_con_tablas(pagina_plumber) if len(texto) else None
        partes = partes_tabla if partes_tabla is not None else ([Parte(texto)] if texto else [])
        resultado = PaginaExtraida(
            numero=numero,
            metodo=MetodoExtraccion.NATIVE,
            partes=partes,
            has_tables=partes_tabla is not None,
        )

    resultado.has_visual_elements = clasif.has_visual_elements
    resultado.has_signatures_or_stamps = clasif.has_visual_elements and (
        clasif.posible_sello or tiene_vocabulario_firma(resultado.texto)
    )
    return resultado


def extraer_documento(ruta: str, cfg: ConfigExtraccion) -> ResultadoExtraccion:
    paginas: list[PaginaExtraida] = []
    documento = pdfium.PdfDocument(ruta)
    try:
        with pdfplumber.open(ruta) as plumber:
            for i in range(len(documento)):
                pagina = documento[i]
                pagina_plumber = plumber.pages[i]
                try:
                    paginas.append(_extraer_pagina(i + 1, pagina, pagina_plumber, cfg))
                finally:
                    pagina.close()
                    pagina_plumber.close()  # libera la caché de objetos de pdfminer
    finally:
        documento.close()

    usa_ocr = any(p.metodo == MetodoExtraccion.OCR for p in paginas)
    return ResultadoExtraccion(
        paginas=paginas, ocr_version=version_tesseract() if usa_ocr else None
    )
