"""Generadores de PDFs de prueba en memoria (los .pdf no se versionan)."""

import io

from pypdf import PdfWriter

A4 = (595.0, 842.0)


def pdf(
    paginas: int = 3, user_password: str | None = None, owner_password: str | None = None
) -> bytes:
    """PDF de páginas en blanco (sin texto)."""
    writer = PdfWriter()
    for _ in range(paginas):
        writer.add_blank_page(width=A4[0], height=A4[1])
    if user_password is not None or owner_password is not None:
        writer.encrypt(user_password=user_password or "", owner_password=owner_password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _envolver(texto: str, ancho: int = 95) -> list[str]:
    lineas: list[str] = []
    for parrafo in texto.split("\n"):
        actual = ""
        for palabra in parrafo.split():
            if len(actual) + len(palabra) + 1 > ancho:
                lineas.append(actual)
                actual = palabra
            else:
                actual = f"{actual} {palabra}".strip()
        lineas.append(actual)
    return lineas


def pdf_texto(paginas: list[str], fuente_pt: int = 9) -> bytes:
    """Cada elemento es el texto de una página. Las líneas vacías separan párrafos."""
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for texto in paginas:
        y = A4[1] - 50
        c.setFont("Helvetica", fuente_pt)
        for linea in _envolver(texto):
            if y < 40:
                break
            c.drawString(40, y, linea)
            y -= fuente_pt + 3
        c.showPage()
    c.save()
    return buf.getvalue()


def pdf_tabla(titulo: str, filas: list[list[str]], texto_final: str = "") -> bytes:
    """Página con un párrafo, una tabla con bordes (detectable por pdfplumber) y otro párrafo."""
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    estilos = getSampleStyleSheet()
    tabla = Table(filas)
    tabla.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.8, colors.black)]))
    elementos = [Paragraph(titulo, estilos["Normal"]), Spacer(1, 12), tabla]
    if texto_final:
        elementos += [Spacer(1, 12), Paragraph(texto_final, estilos["Normal"])]
    doc.build(elementos)
    return buf.getvalue()


def _imagen_png(ancho: int, alto: int, color=(200, 30, 30)) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (ancho, alto), "white")
    ImageDraw.Draw(img).ellipse((5, 5, ancho - 5, alto - 5), outline=color, width=6)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def pdf_con_sello(texto: str) -> bytes:
    """Página de texto con una imagen pequeña tipo sello (≈2 % del área)."""
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 10)
    y = A4[1] - 60
    for linea in _envolver(texto):
        c.drawString(40, y, linea)
        y -= 13
    c.drawImage(ImageReader(io.BytesIO(_imagen_png(200, 200))), 400, 80, width=90, height=90)
    c.showPage()
    c.save()
    return buf.getvalue()


def pdf_escaneado(texto: str, dpi: int = 200) -> bytes:
    """Simula un escaneo: genera el texto, lo rasteriza y deja solo la imagen (sin texto nativo)."""
    import pypdfium2 as pdfium
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    original = pdfium.PdfDocument(pdf_texto([texto], fuente_pt=14))
    try:
        imagen = original[0].render(scale=dpi / 72).to_pil()
    finally:
        original.close()
    png = io.BytesIO()
    imagen.save(png, format="PNG")

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawImage(ImageReader(io.BytesIO(png.getvalue())), 0, 0, width=A4[0], height=A4[1])
    c.showPage()
    c.save()
    return buf.getvalue()


def unir(*pdfs: bytes) -> bytes:
    from pypdf import PdfReader

    writer = PdfWriter()
    for contenido in pdfs:
        for pagina in PdfReader(io.BytesIO(contenido)).pages:
            writer.add_page(pagina)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def texto_largo(n_oraciones: int, tema: str = "suministro") -> str:
    """Texto de pliego verosímil con oraciones distintas (para medir tokens)."""
    plantillas = [
        "El oferente deberá acreditar el registro sanitario INVIMA vigente para el ítem {i} del {t}.",
        "La entrega del lote {i} se realizará en el almacén central dentro de los {i} días hábiles siguientes.",
        "El precio unitario del ítem {i} incluirá transporte, seguros y cadena de frío cuando aplique.",
        "La entidad podrá verificar la ficha técnica del equipo {i} antes de la adjudicación del {t}.",
        "Las garantías de calidad del producto {i} tendrán una vigencia mínima de doce meses.",
    ]
    return " ".join(
        plantillas[i % len(plantillas)].format(i=i + 1, t=tema) for i in range(n_oraciones)
    )
