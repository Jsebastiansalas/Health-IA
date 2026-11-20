"""Directorio aislado donde vive temporalmente cada PDF mientras se indexa.

El nombre del archivo es siempre {documento_id}.pdf: nunca se usa el nombre original del
cliente para construir rutas.
"""

import logging
import os
import uuid
from pathlib import Path

from app.core.config import get_settings

log = logging.getLogger(__name__)

SUFIJO_PARCIAL = ".part"


def directorio() -> Path:
    d = get_settings().ephemeral_dir
    d.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        d.chmod(0o700)
    return d


def ruta_pdf(documento_id: uuid.UUID) -> Path:
    return directorio() / f"{documento_id}.pdf"


def ruta_parcial(documento_id: uuid.UUID) -> Path:
    return directorio() / f"{documento_id}{SUFIJO_PARCIAL}"


def borrar(ruta: Path) -> bool:
    """Equivalente a Files.deleteIfExists. Devuelve True si el archivo existía."""
    try:
        ruta.unlink()
        return True
    except FileNotFoundError:
        return False


def documento_id_de(ruta: Path) -> uuid.UUID | None:
    nombre = ruta.name.removesuffix(SUFIJO_PARCIAL).removesuffix(".pdf")
    try:
        return uuid.UUID(nombre)
    except ValueError:
        return None
