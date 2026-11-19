"""Generadores de PDFs de prueba en memoria (los .pdf no se versionan)."""

import io

from pypdf import PdfWriter

# Marcador que el antivirus simulado de las pruebas trata como virus.
MARCADOR_VIRUS = b"MEDTENDER-MARCADOR-VIRUS-DE-PRUEBA"


def pdf(
    paginas: int = 3, user_password: str | None = None, owner_password: str | None = None
) -> bytes:
    writer = PdfWriter()
    for _ in range(paginas):
        writer.add_blank_page(width=595, height=842)
    if user_password is not None or owner_password is not None:
        writer.encrypt(user_password=user_password or "", owner_password=owner_password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()
