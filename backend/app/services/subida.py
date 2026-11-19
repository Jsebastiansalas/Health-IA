"""Recepción multipart en streaming.

A diferencia de UploadFile, que primero copia el archivo completo a un temporal del sistema,
aquí cada bloque se escribe directamente en el directorio efímero mientras se calcula el
SHA-256, y la subida se corta en cuanto supera el tamaño máximo.
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import Request, status
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import MultipartParser, parse_options_header

from app.services import almacen_efimero

CAMPO_ARCHIVO = "archivo"
_MAX_CAMPO_TEXTO = 1024
_MAX_CAMPOS = 10
_HOLGURA_MULTIPART = 64 * 1024  # cabeceras y campos de texto del multipart


class SubidaInvalida(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass
class ArchivoRecibido:
    ruta: Path
    sha256: str
    tamano: int
    nombre_original: str
    cabecera: bytes
    campos: dict[str, str] = field(default_factory=dict)


class _Receptor:
    def __init__(self, destino: Path, max_bytes: int):
        self.destino = destino
        self.max_bytes = max_bytes
        self.hash = hashlib.sha256()
        self.tamano = 0
        self.cabecera = b""
        self.nombre_original: str | None = None
        self.campos: dict[str, str] = {}
        self.error: SubidaInvalida | None = None
        self._archivo = None
        self._header_field = b""
        self._header_value = b""
        self._headers: dict[bytes, bytes] = {}
        self._parte_nombre: str | None = None
        self._parte_es_archivo = False
        self._buffer_texto = bytearray()

    # --- callbacks de python-multipart ---
    def on_part_begin(self) -> None:
        self._headers = {}
        self._parte_nombre = None
        self._parte_es_archivo = False
        self._buffer_texto = bytearray()

    def on_header_field(self, data: bytes, start: int, end: int) -> None:
        self._header_field += data[start:end]

    def on_header_value(self, data: bytes, start: int, end: int) -> None:
        self._header_value += data[start:end]

    def on_header_end(self) -> None:
        self._headers[self._header_field.lower()] = self._header_value
        self._header_field = b""
        self._header_value = b""

    def on_headers_finished(self) -> None:
        _, params = parse_options_header(self._headers.get(b"content-disposition", b""))
        nombre = params.get(b"name", b"").decode("utf-8", "replace")
        self._parte_nombre = nombre
        if b"filename" in params:
            if nombre != CAMPO_ARCHIVO or self._archivo is not None or self.nombre_original:
                self._fallar(status.HTTP_400_BAD_REQUEST, "Se espera un único archivo en 'archivo'")
                return
            filename = params[b"filename"].decode("utf-8", "replace")
            # Solo se conserva el nombre base como metadato; nunca se usa como ruta.
            self.nombre_original = Path(filename.replace("\\", "/")).name[:255] or "documento.pdf"
            self._parte_es_archivo = True
            self._archivo = self.destino.open("xb")
        elif len(self.campos) >= _MAX_CAMPOS:
            self._fallar(status.HTTP_400_BAD_REQUEST, "Demasiados campos en el formulario")

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self.error:
            return
        trozo = data[start:end]
        if self._parte_es_archivo:
            self.tamano += len(trozo)
            if self.tamano > self.max_bytes:
                self._fallar(
                    status.HTTP_413_CONTENT_TOO_LARGE,
                    f"El archivo supera el máximo de {self.max_bytes // (1024 * 1024)} MB",
                )
                return
            if len(self.cabecera) < 1024:
                self.cabecera += trozo[: 1024 - len(self.cabecera)]
            self.hash.update(trozo)
            assert self._archivo is not None
            self._archivo.write(trozo)
        else:
            self._buffer_texto += trozo
            if len(self._buffer_texto) > _MAX_CAMPO_TEXTO:
                self._fallar(status.HTTP_400_BAD_REQUEST, "Campo de formulario demasiado largo")

    def on_part_end(self) -> None:
        if self.error:
            return
        if self._parte_es_archivo:
            self._cerrar_archivo()
        elif self._parte_nombre:
            self.campos[self._parte_nombre] = self._buffer_texto.decode("utf-8", "replace")

    # --- utilidades ---
    def _fallar(self, status_code: int, detail: str) -> None:
        if self.error is None:
            self.error = SubidaInvalida(status_code, detail)

    def _cerrar_archivo(self) -> None:
        if self._archivo is not None and not self._archivo.closed:
            self._archivo.close()

    def callbacks(self) -> dict:
        return {
            "on_part_begin": self.on_part_begin,
            "on_header_field": self.on_header_field,
            "on_header_value": self.on_header_value,
            "on_header_end": self.on_header_end,
            "on_headers_finished": self.on_headers_finished,
            "on_part_data": self.on_part_data,
            "on_part_end": self.on_part_end,
        }


async def recibir_pdf(request: Request, destino: Path, max_bytes: int) -> ArchivoRecibido:
    """Recibe el multipart en `destino`. Si algo falla, `destino` no queda en disco."""
    content_type, params = parse_options_header(request.headers.get("content-type", ""))
    if content_type != b"multipart/form-data" or b"boundary" not in params:
        raise SubidaInvalida(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Se espera multipart/form-data"
        )
    longitud = request.headers.get("content-length")
    if longitud and longitud.isdigit() and int(longitud) > max_bytes + _HOLGURA_MULTIPART:
        raise SubidaInvalida(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"El archivo supera el máximo de {max_bytes // (1024 * 1024)} MB",
        )

    receptor = _Receptor(destino, max_bytes)
    parser = MultipartParser(params[b"boundary"], receptor.callbacks())
    try:
        try:
            async for bloque in request.stream():
                parser.write(bloque)
                if receptor.error:
                    raise receptor.error
            parser.finalize()
        except MultipartParseError as exc:
            raise SubidaInvalida(status.HTTP_400_BAD_REQUEST, "Multipart mal formado") from exc
        if receptor.error:
            raise receptor.error
        if receptor.nombre_original is None:
            raise SubidaInvalida(status.HTTP_400_BAD_REQUEST, "Falta el archivo 'archivo'")
        if receptor.tamano == 0:
            raise SubidaInvalida(status.HTTP_400_BAD_REQUEST, "El archivo está vacío")
    except BaseException:
        receptor._cerrar_archivo()
        almacen_efimero.borrar(destino)
        raise
    finally:
        receptor._cerrar_archivo()

    return ArchivoRecibido(
        ruta=destino,
        sha256=receptor.hash.hexdigest(),
        tamano=receptor.tamano,
        nombre_original=receptor.nombre_original,
        cabecera=receptor.cabecera,
        campos=receptor.campos,
    )
