"""Extracción página a página con PDFs reales generados en memoria (sin base de datos)."""

import pytest

from app.pipeline import extraccion, secciones, tablas
from app.pipeline.extraccion import clasificar_pagina, extraer_documento, tesseract_disponible
from app.pipeline.modelos import ConfigExtraccion, MetodoExtraccion
from tests.pdfs import (
    pdf,
    pdf_con_sello,
    pdf_escaneado,
    pdf_escaneado_bajo_contraste,
    pdf_escaneado_rotado,
    pdf_tabla,
    pdf_texto,
    unir,
)

CFG = ConfigExtraccion()


@pytest.fixture
def extraer(tmp_path):
    def _extraer(contenido: bytes):
        ruta = tmp_path / "doc.pdf"
        ruta.write_bytes(contenido)
        return extraer_documento(str(ruta), CFG)

    return _extraer


# ---------- Decisiones puras ----------
def test_clasificacion_de_paginas():
    # Texto nativo suficiente: nunca OCR, aunque haya una imagen grande.
    assert not clasificar_pagina(500, [0.9], CFG).usar_ocr
    # Sin texto y con imagen a página completa: escaneo -> OCR.
    c = clasificar_pagina(10, [0.98], CFG)
    assert c.usar_ocr and c.has_visual_elements and not c.posible_sello
    # Sin texto y sin imágenes: página en blanco, no se gasta OCR.
    assert not clasificar_pagina(0, [], CFG).usar_ocr
    # Imagen pequeña (sello o firma) en página con texto.
    c = clasificar_pagina(800, [0.03], CFG)
    assert c.has_visual_elements and c.posible_sello and not c.usar_ocr
    # Iconos diminutos no cuentan como elemento visual relevante.
    assert not clasificar_pagina(800, [0.001], CFG).has_visual_elements


def test_vocabulario_de_firma():
    assert extraccion.tiene_vocabulario_firma("Firmado por el Representante Legal")
    assert extraccion.tiene_vocabulario_firma("Autenticación ante Notaría 12")
    assert not extraccion.tiene_vocabulario_firma("Cuadro de precios unitarios")


def test_encabezados_de_seccion():
    assert secciones.es_encabezado("CAPÍTULO III - CONDICIONES TÉCNICAS")
    assert secciones.es_encabezado("Cláusula 5. Garantías")
    assert secciones.es_encabezado("ADENDA No. 2")
    assert secciones.es_encabezado("FICHA TECNICA DEL EQUIPO")
    assert secciones.es_encabezado("Cláusula primera: objeto")
    assert secciones.es_encabezado("Anexo A")
    assert secciones.es_encabezado("Antecedentes")
    assert secciones.es_encabezado("Artículo 12")
    assert not secciones.es_encabezado("El oferente presentará el anexo técnico.")
    # Líneas de texto corrido cortadas por el ajuste de línea del PDF (falsos positivos reales).
    assert not secciones.es_encabezado(
        "ficha técnica del equipo 24 antes de la adjudicación del suministro."
    )
    assert not secciones.es_encabezado(
        "Ficha técnica del equipo antes de la adjudicación del suministro."
    )
    assert not secciones.es_encabezado(
        "Anexo técnico deberá presentarse firmado por el representante legal"
    )
    # Oración larga que empieza por palabra clave: no es encabezado.
    assert not secciones.es_encabezado("Cláusula penal: " + "el contratista pagará " * 20)


def test_tabla_a_markdown():
    md = tablas.a_markdown(
        [["Código", "Precio"], ["CUM-1", "10|20"], [None, None], ["ATC\nL01", None]]
    )
    assert md == "| Código | Precio |\n| --- | --- |\n| CUM-1 | 10\\|20 |\n| ATC L01 |  |"
    assert tablas.a_markdown([[None], []]) == ""


# ---------- PDFs reales ----------
def test_pagina_nativa(extraer):
    r = extraer(
        pdf_texto(["CAPÍTULO 1 OBJETO\n\nSuministro de medicamentos oncológicos para el hospital."])
    )
    assert len(r.paginas) == 1 and r.ocr_version is None
    p = r.paginas[0]
    assert p.metodo == MetodoExtraccion.NATIVE
    assert "Suministro de medicamentos oncológicos" in p.texto
    assert not p.has_tables and not p.has_visual_elements and not p.has_signatures_or_stamps


def test_pagina_en_blanco(extraer):
    r = extraer(pdf(paginas=1))
    assert r.paginas[0].metodo == MetodoExtraccion.NATIVE
    assert r.paginas[0].partes == []


def test_tabla_se_convierte_a_markdown_en_orden(extraer):
    filas = [
        ["Código CUM", "Principio activo", "Concentración", "Precio unitario"],
        ["19912345-1", "Paclitaxel", "6 mg/ml", "$ 125.000"],
        ["20045678-2", "Carboplatino", "10 mg/ml", "$ 98.500"],
    ]
    r = extraer(pdf_tabla("CUADRO DE MEDICAMENTOS DEL LOTE 1", filas, "Los precios incluyen IVA."))
    p = r.paginas[0]
    assert p.has_tables
    tipos = [parte.es_tabla for parte in p.partes]
    assert tipos == [False, True, False]  # párrafo, tabla, párrafo
    tabla = p.partes[1].texto
    assert (
        tabla.splitlines()[0]
        == "| Código CUM | Principio activo | Concentración | Precio unitario |"
    )
    assert tabla.splitlines()[1] == "| --- | --- | --- | --- |"
    assert "| 19912345-1 | Paclitaxel | 6 mg/ml | $ 125.000 |" in tabla
    # El contenido de la tabla no se duplica como texto suelto.
    assert "Paclitaxel" not in p.partes[0].texto + p.partes[2].texto


def test_sello_marca_elementos_visuales(extraer):
    r = extraer(pdf_con_sello("Certificado de experiencia expedido por la Clínica del Norte. " * 3))
    p = r.paginas[0]
    assert p.metodo == MetodoExtraccion.NATIVE
    assert p.has_visual_elements and p.has_signatures_or_stamps


def test_pagina_escaneada_va_a_ocr(extraer, monkeypatch):
    """Comprueba la decisión con un escaneo real; el OCR se simula si no hay Tesseract."""
    llamadas = []

    def ocr_falso(pagina, cfg):
        llamadas.append(pagina)
        return "REGISTRO SANITARIO INVIMA 2024M-0001234\n\nFirmado: director técnico", 0.91

    monkeypatch.setattr(extraccion, "_ocr", ocr_falso)
    monkeypatch.setattr(extraccion, "version_tesseract", lambda: "tesseract-5.3-v1")

    nativa = pdf_texto(["Página nativa con texto suficiente para no requerir OCR en absoluto."])
    r = extraer(unir(nativa, pdf_escaneado("REGISTRO SANITARIO INVIMA")))

    assert len(llamadas) == 1  # solo la página escaneada se rasteriza
    assert [p.metodo for p in r.paginas] == [MetodoExtraccion.NATIVE, MetodoExtraccion.OCR]
    escaneada = r.paginas[1]
    assert escaneada.ocr_confidence == 0.91
    assert escaneada.has_visual_elements
    assert escaneada.has_signatures_or_stamps  # vocabulario "Firmado"
    assert r.ocr_version == "tesseract-5.3-v1"


@pytest.mark.skipif(not tesseract_disponible(), reason="Tesseract no instalado (corre en Docker)")
def test_ocr_real_en_espanol(extraer):
    r = extraer(pdf_escaneado("REGISTRO SANITARIO INVIMA 2024M-0001234\n\nPaclitaxel 6 mg/ml"))
    p = r.paginas[0]
    assert p.metodo == MetodoExtraccion.OCR
    assert "INVIMA" in p.texto and "Paclitaxel" in p.texto
    assert p.ocr_confidence is not None and p.ocr_confidence > 0.6


# ---------- Sprint 16: OCR con reintento, rotación y bajo contraste ----------
def test_grados_de_rotacion_desde_osd():
    osd = "Page number: 0\nOrientation in degrees: 90\nRotate: 270\nOrientation confidence: 4.1"
    assert extraccion.grados_de_rotacion(osd) == 270
    assert extraccion.grados_de_rotacion("Rotate: 0") == 0
    assert extraccion.grados_de_rotacion("Rotate: 45") == 0  # valor no válido: se ignora
    assert extraccion.grados_de_rotacion("") == 0


def test_preprocesar_binariza_un_escaneo_tenue():
    from PIL import Image

    tenue = Image.new("L", (40, 40), 200)
    for x in range(10, 30):
        tenue.putpixel((x, 20), 150)  # trazo gris sobre fondo gris
    binaria = extraccion.preprocesar(tenue.convert("RGB"))
    valores = set(binaria.tobytes())
    assert valores <= {0, 255} and valores == {0, 255}  # solo blanco y negro, trazo conservado


def _pagina_falsa(monkeypatch, imagen):
    class Render:
        def to_pil(self):
            return imagen

    class Pagina:
        def render(self, scale):
            return Render()

    return Pagina()


def test_ocr_no_reintenta_si_la_confianza_es_buena(monkeypatch):
    from PIL import Image

    lecturas = []
    monkeypatch.setattr(
        extraccion, "_leer", lambda img, cfg: (lecturas.append(1), ("texto claro", 0.93))[1]
    )
    pagina = _pagina_falsa(monkeypatch, Image.new("RGB", (10, 10), "white"))
    assert extraccion._ocr(pagina, CFG) == ("texto claro", 0.93)
    assert len(lecturas) == 1


def test_ocr_reintenta_con_rotacion_y_conserva_el_mejor(monkeypatch):
    from PIL import Image

    base = Image.new("RGB", (30, 10), "white")  # ancha: al girar 90° queda alta (10x30)

    def leer(img, cfg):
        return ("ilegible", 0.31) if img.size == (30, 10) else ("texto bien leído", 0.9)

    monkeypatch.setattr(extraccion, "_leer", leer)
    monkeypatch.setattr(extraccion, "_rotacion_detectada", lambda img, cfg: 90)
    assert extraccion._ocr(_pagina_falsa(monkeypatch, base), CFG) == ("texto bien leído", 0.9)


def test_ocr_nunca_empeora_con_el_reintento(monkeypatch):
    from PIL import Image

    respuestas = iter([("lectura original", 0.60), ("peor", 0.40), ("peor aún", 0.20)])
    monkeypatch.setattr(extraccion, "_leer", lambda img, cfg: next(respuestas))
    monkeypatch.setattr(extraccion, "_rotacion_detectada", lambda img, cfg: 180)
    pagina = _pagina_falsa(monkeypatch, Image.new("RGB", (10, 10), "white"))
    assert extraccion._ocr(pagina, CFG) == ("lectura original", 0.60)


def test_ocr_sin_texto_no_gana_a_uno_con_texto(monkeypatch):
    from PIL import Image

    respuestas = iter([("", None), ("algo legible", 0.55), ("algo legible", 0.55)])
    monkeypatch.setattr(extraccion, "_leer", lambda img, cfg: next(respuestas))
    monkeypatch.setattr(extraccion, "_rotacion_detectada", lambda img, cfg: 0)
    pagina = _pagina_falsa(monkeypatch, Image.new("RGB", (10, 10), "white"))
    assert extraccion._ocr(pagina, CFG)[0] == "algo legible"


def test_paginas_rotadas_y_tenues_se_clasifican_como_escaneadas(extraer, monkeypatch):
    monkeypatch.setattr(extraccion, "_ocr", lambda pagina, cfg: ("texto", 0.8))
    monkeypatch.setattr(extraccion, "version_tesseract", lambda: "tesseract-5.3-v1")
    for contenido in (
        pdf_escaneado_rotado("REGISTRO SANITARIO INVIMA", 90),
        pdf_escaneado_rotado("REGISTRO SANITARIO INVIMA", 180),
        pdf_escaneado_bajo_contraste("REGISTRO SANITARIO INVIMA"),
    ):
        assert extraer(contenido).paginas[0].metodo == MetodoExtraccion.OCR


@pytest.mark.skipif(not tesseract_disponible(), reason="Tesseract no instalado (corre en Docker)")
@pytest.mark.parametrize("grados", [90, 180, 270])
def test_ocr_real_lee_paginas_rotadas(extraer, grados):
    r = extraer(pdf_escaneado_rotado("REGISTRO SANITARIO INVIMA 2024M-0001234\n\nPaclitaxel", grados))
    assert "INVIMA" in r.paginas[0].texto


@pytest.mark.skipif(not tesseract_disponible(), reason="Tesseract no instalado (corre en Docker)")
def test_ocr_real_lee_escaneo_de_bajo_contraste(extraer):
    r = extraer(pdf_escaneado_bajo_contraste("REGISTRO SANITARIO INVIMA 2024M-0001234"))
    assert "INVIMA" in r.paginas[0].texto


# ---------- Fidelidad de tablas ----------
@pytest.mark.parametrize(
    "filas",
    [
        [["Código", "Producto", "Cantidad"], ["1", "Paclitaxel 6 mg/ml", "120"], ["2", "Cisplatino", "45"]],
        [["CUM", "Descripción", "Precio", "IVA"], *[[f"{i}-1", f"Ítem {i}", f"$ {i * 1000}", "0 %"] for i in range(1, 12)]],
        [["Ref", "Observación"], ["A", "Texto con barra | vertical"], ["B", "Acción: «urgente»"]],
    ],
)
def test_tabla_conserva_todas_las_celdas(extraer, filas):
    r = extraer(pdf_tabla("CUADRO DE PRUEBA", filas))
    tabla = next(p.texto for p in r.paginas[0].partes if p.es_tabla)
    esperadas = tablas.filas_limpias(filas)
    obtenidas = [
        [c.strip() for c in linea.strip("|").split(" | ")]
        for linea in tabla.splitlines()
        if not linea.startswith("| ---")
    ]
    assert len(obtenidas) == len(esperadas)  # ninguna fila perdida ni duplicada
    for fila_obtenida, fila_esperada in zip(obtenidas, esperadas, strict=True):
        assert fila_obtenida == fila_esperada  # `|` escapado como `\|` en ambos lados
