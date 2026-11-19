"""Estructuras que viajan entre extracción (proceso aparte), fragmentación y persistencia.

Deben ser serializables con pickle porque la extracción corre en un ProcessPoolExecutor.
"""

from dataclasses import dataclass, field
from enum import StrEnum

EXTRACTOR_VERSION = "pdfium-pdfplumber-v1"


class MetodoExtraccion(StrEnum):
    NATIVE = "NATIVE"
    OCR = "OCR"
    MIXED = "MIXED"


@dataclass(frozen=True)
class Parte:
    """Trozo de contenido de una página en orden de lectura."""

    texto: str
    es_tabla: bool = False


@dataclass
class PaginaExtraida:
    numero: int
    metodo: MetodoExtraccion
    partes: list[Parte] = field(default_factory=list)
    ocr_confidence: float | None = None
    has_tables: bool = False
    has_visual_elements: bool = False
    has_signatures_or_stamps: bool = False

    @property
    def texto(self) -> str:
        return "\n\n".join(p.texto for p in self.partes)


@dataclass(frozen=True)
class ConfigExtraccion:
    umbral_texto_nativo: int = 60
    ocr_dpi: int = 300
    ocr_idioma: str = "spa"
    imagen_relevante_min_area: float = 0.01
    imagen_escaneo_min_area: float = 0.30
    imagen_sello_max_area: float = 0.15


@dataclass
class ResultadoExtraccion:
    paginas: list[PaginaExtraida]
    ocr_version: str | None = None  # p. ej. "tesseract-5.3-v1" si alguna página usó OCR


@dataclass(frozen=True)
class ConfigFragmentacion:
    min_tokens: int = 500
    max_tokens: int = 1000
    overlap_ratio: float = 0.15


@dataclass
class FragmentoGenerado:
    orden: int
    pagina_inicio: int
    pagina_fin: int
    seccion: str
    texto: str
    token_count: int
    metadata: dict
