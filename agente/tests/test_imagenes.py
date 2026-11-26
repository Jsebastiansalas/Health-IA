"""Fotos y escaneos de documentos (JPG, PNG, HEIC): extracción con OCR y rechazos que explican qué hacer."""

import pickle
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from PIL import Image
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.core.enums import EstadoIndexacion as E
from app.models import ActaPurga, Documento, Fragmento
from app.pipeline import extraccion
from app.pipeline.extraccion import ImagenNoLegible, extraer_documento
from app.pipeline.modelos import ConfigExtraccion, MetodoExtraccion
from app.pipeline.procesador import procesar_documento
from tests.fakes import archivos, subir
from tests.pdfs import _imagen_de_texto

CFG = ConfigExtraccion()
TEXTO = "RESULTADO DE LABORATORIO\nHemoglobina 13,2 g/dL\nGlucosa 92 mg/dL en ayunas"


@pytest.fixture(autouse=True)
def ocr_simulado(monkeypatch):
    """Sin Tesseract en este equipo: se simula la lectura, no la decisión de qué hacer con ella."""
    monkeypatch.setattr(extraccion, "version_tesseract", lambda: "tesseract-5.3-v1")
    monkeypatch.setattr(extraccion, "_rotacion_detectada", lambda img, cfg: 0)
    vistas: list[Image.Image] = []

    def leer(imagen, cfg):
        vistas.append(imagen)
        return TEXTO, 0.91

    monkeypatch.setattr(extraccion, "_leer", leer)
    return vistas


def guardar(tmp_path, imagen: Image.Image, nombre: str, **kw) -> str:
    ruta = tmp_path / nombre
    imagen.save(ruta, **kw)
    return str(ruta)


def test_una_foto_png_se_lee_como_una_pagina_de_ocr(tmp_path, ocr_simulado):
    ruta = guardar(tmp_path, _imagen_de_texto("Hemoglobina 13,2"), "resultado.png")
    r = extraer_documento(ruta, CFG)
    assert len(r.paginas) == 1 and r.ocr_version == "tesseract-5.3-v1"
    p = r.paginas[0]
    assert p.metodo == MetodoExtraccion.OCR and p.numero == 1
    assert "Hemoglobina" in p.texto and p.ocr_confidence == 0.91
    assert not p.has_visual_elements  # la foto ES el documento: no es una «imagen» dentro de uno


def test_una_foto_jpg_tambien(tmp_path):
    ruta = guardar(tmp_path, _imagen_de_texto("x"), "orden.jpg", quality=90)
    assert extraer_documento(ruta, CFG).paginas[0].texto.startswith("RESULTADO")


def test_una_foto_heic_se_lee(tmp_path):
    pillow_heif = pytest.importorskip("pillow_heif")
    pillow_heif.register_heif_opener()
    ruta = guardar(tmp_path, _imagen_de_texto("x"), "foto.heic")
    assert extraer_documento(ruta, CFG).paginas[0].metodo == MetodoExtraccion.OCR


def test_la_orientacion_exif_se_corrige_antes_del_ocr(tmp_path, ocr_simulado):
    """Los móviles guardan la foto girada y lo dicen en EXIF: sin corregirlo el texto sale tumbado."""
    imagen = Image.new("RGB", (200, 100), "white")  # apaisada
    exif = Image.Exif()
    exif[0x0112] = 6  # «girar 90° para verla derecha»
    ruta = guardar(tmp_path, imagen, "movil.jpg", exif=exif)
    extraer_documento(ruta, CFG)
    assert ocr_simulado[0].size == (100, 200)  # ahora vertical


def test_una_foto_enorme_se_reduce_antes_del_ocr(tmp_path, ocr_simulado):
    ruta = guardar(tmp_path, Image.new("RGB", (6400, 3000), "white"), "grande.png")
    extraer_documento(ruta, CFG)
    assert max(ocr_simulado[0].size) == CFG.imagen_max_lado


def test_una_imagen_sin_texto_como_una_radiografia_explica_que_hacer(tmp_path, monkeypatch):
    monkeypatch.setattr(extraccion, "_leer", lambda img, cfg: ("", None))
    ruta = guardar(tmp_path, Image.new("RGB", (400, 400), "gray"), "radiografia.png")
    with pytest.raises(ImagenNoLegible) as e:
        extraer_documento(ruta, CFG)
    assert "no interpreta imágenes médicas" in str(e.value)
    assert "informe" in str(e.value)


def test_unos_pocos_caracteres_sueltos_tampoco_son_un_documento(tmp_path, monkeypatch):
    monkeypatch.setattr(extraccion, "_leer", lambda img, cfg: ("L R 12", 0.9))
    ruta = guardar(tmp_path, Image.new("RGB", (400, 400), "gray"), "marca.png")
    with pytest.raises(ImagenNoLegible, match="no contiene texto legible"):
        extraer_documento(ruta, CFG)


def test_una_foto_borrosa_se_rechaza_con_su_confianza_y_como_repetirla(tmp_path, monkeypatch):
    monkeypatch.setattr(extraccion, "_leer", lambda img, cfg: (TEXTO, 0.30))
    ruta = guardar(tmp_path, Image.new("RGB", (400, 400), "white"), "borrosa.png")
    with pytest.raises(ImagenNoLegible) as e:
        extraer_documento(ruta, CFG)
    mensaje = str(e.value)
    assert "muy poca claridad" in mensaje and "30%" in mensaje and "buena luz" in mensaje


def test_una_lectura_mediocre_pero_usable_se_acepta_y_queda_marcada_para_verificar(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(extraccion, "_leer", lambda img, cfg: (TEXTO, 0.60))
    ruta = guardar(tmp_path, Image.new("RGB", (400, 400), "white"), "regular.png")
    assert extraer_documento(ruta, CFG).paginas[0].ocr_confidence == 0.60  # las citas lo avisarán


def test_un_archivo_danado_con_extension_de_imagen_se_rechaza_con_un_mensaje_claro(tmp_path):
    ruta = tmp_path / "rota.png"
    ruta.write_bytes(b"\x89PNG\r\n\x1a\n" + b"basura" * 50)
    with pytest.raises(ImagenNoLegible, match="No se pudo abrir la imagen"):
        extraer_documento(str(ruta), CFG)


def test_el_error_se_puede_enviar_entre_procesos_con_su_mensaje():
    """La extracción corre en un ProcessPoolExecutor: la excepción viaja serializada."""
    e = pickle.loads(pickle.dumps(ImagenNoLegible("mensaje para la persona")))
    assert isinstance(e, ImagenNoLegible) and str(e) == "mensaje para la persona"


# ---------- pipeline completo con una foto ----------
class VectorizadorFalso:
    def __init__(self):
        self.llamadas: list[uuid.UUID] = []

    async def vectorizar(self, sessionmaker, documento_id):
        self.llamadas.append(documento_id)


@pytest.fixture
def ejecutor():
    with ThreadPoolExecutor(max_workers=1) as ex:
        yield ex


def _bytes_png() -> bytes:
    import io

    buf = io.BytesIO()
    _imagen_de_texto("x").save(buf, format="PNG")
    return buf.getvalue()


async def test_una_foto_se_procesa_y_el_temporal_se_borra_con_su_extension(
    org_a, cola, ejecutor, ephemeral_dir
):
    expediente = await org_a.crear_expediente(org_a.admin)
    r = await subir(
        expediente["id"], _bytes_png(), tipo="HISTORIA_CLINICA", nombre="examen.png", formato="PNG"
    )
    doc_id = uuid.UUID(r.json()["id"])
    assert archivos(ephemeral_dir) == [f"{doc_id}.png"]

    vectorizador = VectorizadorFalso()
    await procesar_documento(get_sessionmaker(), doc_id, ejecutor, vectorizador)

    async with get_sessionmaker()() as s:
        d = await s.get(Documento, doc_id)
        frags = (await s.scalars(select(Fragmento).where(Fragmento.documento_id == doc_id))).all()
    assert d.estado_indexacion == E.VECTORIZANDO and d.formato == "PNG"
    assert d.extractor_version == "pillow-tesseract-v1" and d.ocr_version == "tesseract-5.3-v1"
    assert d.total_paginas == 1 and d.paginas_ocr == 1
    assert frags and all(f.metadata_jsonb["extraction_method"] == "OCR" for f in frags)
    assert all(f.metadata_jsonb["ocr_confidence"] == 0.91 for f in frags)
    assert vectorizador.llamadas == [doc_id]


async def test_una_foto_ilegible_se_purga_con_un_motivo_sin_nombres_de_clase_ni_rastro_en_disco(
    org_a, cola, ejecutor, ephemeral_dir, monkeypatch
):
    monkeypatch.setattr(extraccion, "_leer", lambda img, cfg: ("", None))
    expediente = await org_a.crear_expediente(org_a.admin)
    r = await subir(expediente["id"], _bytes_png(), nombre="radiografia.png", formato="PNG")
    doc_id = uuid.UUID(r.json()["id"])

    await procesar_documento(get_sessionmaker(), doc_id, ejecutor, VectorizadorFalso())

    async with get_sessionmaker()() as s:
        d = await s.get(Documento, doc_id)
        actas = (await s.scalars(select(ActaPurga).where(ActaPurga.documento_id == doc_id))).all()
    assert d.estado_indexacion == E.ERROR_PURGADO
    assert "no interpreta imágenes médicas" in d.motivo_error
    assert "ImagenNoLegible" not in d.motivo_error  # mensaje para personas, no para desarrolladores
    assert archivos(ephemeral_dir) == []
    assert len(actas) == 1


async def test_la_purga_y_el_barrido_reconocen_todas_las_extensiones(ephemeral_dir):
    from app.services import almacen_efimero

    doc = uuid.uuid4()
    for ext in (".pdf", ".jpg", ".png", ".heic", ".part"):
        assert almacen_efimero.documento_id_de(ephemeral_dir / f"{doc}{ext}") == doc
        (ephemeral_dir / f"{doc}{ext}").write_bytes(b"x")
    assert almacen_efimero.borrar_documento(doc) is True
    assert archivos(ephemeral_dir) == []
    assert almacen_efimero.borrar_documento(doc) is False
