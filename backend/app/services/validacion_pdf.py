"""Validación estructural del PDF recibido (equivalente a Tika + PDDocument.isEncrypted)."""

import logging
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

log = logging.getLogger(__name__)

# La especificación permite que la cabecera %PDF- aparezca dentro del primer KB.
_VENTANA_CABECERA = 1024


class PdfInvalido(Exception):
    pass


@dataclass(frozen=True)
class InfoPdf:
    total_paginas: int


def tiene_firma_pdf(cabecera: bytes) -> bool:
    return b"%PDF-" in cabecera[:_VENTANA_CABECERA]


def inspeccionar(ruta: Path) -> InfoPdf:
    """Bloqueante: ejecutar con asyncio.to_thread.

    Se rechazan los PDF que piden contraseña para abrirse. Los que solo tienen contraseña de
    propietario (restricciones de impresión/copia, comunes en documentos oficiales) se abren con
    contraseña vacía y el texto es extraíble, así que se aceptan.
    """
    try:
        reader = PdfReader(ruta, strict=False)
        if reader.is_encrypted and not reader.decrypt(""):
            raise PdfInvalido("El PDF está protegido con contraseña")
        total = len(reader.pages)
    except PdfInvalido:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError) as exc:
        raise PdfInvalido(f"PDF corrupto o ilegible: {exc}") from exc
    except Exception as exc:  # pypdf puede lanzar errores variados con archivos dañados
        log.warning("Error inesperado al inspeccionar PDF: %r", exc)
        raise PdfInvalido("PDF corrupto o ilegible") from exc
    if total == 0:
        raise PdfInvalido("El PDF no tiene páginas")
    return InfoPdf(total_paginas=total)
