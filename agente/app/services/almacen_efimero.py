"""Directorio aislado donde vive temporalmente cada documento (PDF o foto) mientras se indexa.

El nombre del archivo es siempre {documento_id}{extensión del formato real}: nunca se usa el
nombre original del cliente para construir rutas.
"""

import logging
import os
import uuid
from pathlib import Path

from app.core.config import get_settings

log = logging.getLogger(__name__)

SUFIJO_PARCIAL = ".part"
EXTENSIONES = {"PDF": ".pdf", "JPG": ".jpg", "PNG": ".png", "HEIC": ".heic"}


def directorio() -> Path:
    d = get_settings().ephemeral_dir
    d.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        d.chmod(0o700)
    return d


def ruta_documento(documento_id: uuid.UUID, formato: str = "PDF") -> Path:
    return directorio() / f"{documento_id}{EXTENSIONES[formato]}"


def ruta_pdf(documento_id: uuid.UUID) -> Path:
    return ruta_documento(documento_id, "PDF")


def ruta_parcial(documento_id: uuid.UUID) -> Path:
    return directorio() / f"{documento_id}{SUFIJO_PARCIAL}"


def borrar(ruta: Path) -> bool:
    """Equivalente a Files.deleteIfExists. Devuelve True si el archivo existía."""
    try:
        ruta.unlink()
        return True
    except FileNotFoundError:
        return False


def borrar_documento(documento_id: uuid.UUID) -> bool:
    """Borra el documento en cualquier formato (y su parcial). True si alguno existía."""
    alguno = False
    for formato in EXTENSIONES:
        alguno |= borrar(ruta_documento(documento_id, formato))
    return borrar(ruta_parcial(documento_id)) or alguno


def documento_id_de(ruta: Path) -> uuid.UUID | None:
    nombre = ruta.name.split(".", 1)[0]  # {id}.pdf, {id}.png, {id}.part…
    try:
        return uuid.UUID(nombre)
    except ValueError:
        return None
