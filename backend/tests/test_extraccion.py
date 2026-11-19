"""Extracción página a página con PDFs reales generados en memoria (sin base de datos)."""

import pytest

from app.pipeline import extraccion, secciones, tablas
from app.pipeline.extraccion import clasificar_pagina, extraer_documento, tesseract_disponible
from app.pipeline.modelos import ConfigExtraccion, MetodoExtraccion
from tests.pdfs import pdf, pdf_con_sello, pdf_escaneado, pdf_tabla, pdf_texto, unir

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
