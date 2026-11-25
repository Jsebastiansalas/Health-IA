"""Cifrado en la base de lo que la persona pregunta y lo que se le responde.

Se hace en el tipo de columna: el resto del agente lee y escribe texto normal. AES-256-GCM con
la clave `DATOS_CLAVE` (32 bytes en base64), que vive en el entorno del servidor y **nunca en la
base**: una copia de la base o un respaldo no bastan para leer el historial. La API Java usa el
mismo formato (`mtd1:` + base64 de vector inicial y texto cifrado) para «Descargar mis datos».

Alcance, a propósito: las preguntas y respuestas guardadas. El texto de los fragmentos **no** se
cifra aquí porque la búsqueda por palabras se calcula en la base a partir de él; esa parte depende
del cifrado del disco.

Perder la clave es perder el historial: hay que guardarla aparte de los respaldos.
"""

import base64
import binascii
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator

PREFIJO = "mtd1:"
_IV = 12
# Lo que queda legible junto a una respuesta cifrada: la huella de los documentos con la que se
# encuentra la línea de tiempo guardada (no dice nada de la persona).
_EN_CLARO = ("huella",)


class ErrorCifrado(Exception):
    pass


class CifradorDatos:
    def __init__(self, clave_base64: str):
        try:
            clave = base64.b64decode(clave_base64.strip(), validate=True)
        except (binascii.Error, ValueError):
            clave = b""
        if len(clave) != 32:
            raise ErrorCifrado("DATOS_CLAVE debe ser de 32 bytes en base64")
        self._aes = AESGCM(clave)

    def cifrar(self, texto: str) -> str:
        iv = os.urandom(_IV)
        return PREFIJO + base64.b64encode(iv + self._aes.encrypt(iv, texto.encode(), None)).decode()

    def descifrar(self, valor: str) -> str:
        try:
            datos = base64.b64decode(valor.removeprefix(PREFIJO), validate=True)
            return self._aes.decrypt(datos[:_IV], datos[_IV:], None).decode()
        except (InvalidTag, binascii.Error, ValueError) as exc:
            raise ErrorCifrado(
                "No se pudo descifrar un dato guardado: ¿cambió DATOS_CLAVE?"
            ) from exc


def clave_configurada() -> str:
    from app.core.config import get_settings  # aquí para no crear un ciclo con la configuración

    return get_settings().datos_clave


def _cifrador() -> CifradorDatos | None:
    clave = clave_configurada()
    return CifradorDatos(clave) if clave else None


def _exigir() -> CifradorDatos:
    cifrador = _cifrador()
    if cifrador is None:
        raise ErrorCifrado("Hay datos cifrados y falta DATOS_CLAVE")
    return cifrador


class TextoCifrado(TypeDecorator):
    """Texto que se guarda cifrado. Lo escrito antes de tener clave se sigue leyendo."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        cifrador = _cifrador()
        return value if value is None or cifrador is None else cifrador.cifrar(value)

    def process_result_value(self, value, dialect):
        if value is None or not value.startswith(PREFIJO):
            return value
        return _exigir().descifrar(value)


class JsonCifrado(TypeDecorator):
    """JSONB cuyo contenido se guarda como {"cifrado": …} (más las claves de `_EN_CLARO`)."""

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value, dialect):
        cifrador = _cifrador()
        if value is None or cifrador is None:
            return value
        envoltura = {k: value[k] for k in _EN_CLARO if k in value}
        envoltura["cifrado"] = cifrador.cifrar(json.dumps(value, ensure_ascii=False))
        return envoltura

    def process_result_value(self, value, dialect):
        if (
            isinstance(value, dict)
            and str(value.get("cifrado", "")).startswith(PREFIJO)
            and set(value) <= {"cifrado", *_EN_CLARO}
        ):
            return json.loads(_exigir().descifrar(value["cifrado"]))
        return value
