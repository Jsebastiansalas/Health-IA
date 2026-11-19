"""Escaneo antivirus enchufable.

ClamavScanner implementa el protocolo INSTREAM de clamd por TCP sin dependencias externas:
  zINSTREAM\\0  +  [longitud big-endian de 4 bytes + bloque]*  +  0x00000000
  respuesta: "stream: OK" | "stream: <firma> FOUND" | "... ERROR"
"""

import asyncio
import logging
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings

log = logging.getLogger(__name__)

_BLOQUE = 64 * 1024


@dataclass(frozen=True)
class ResultadoEscaneo:
    limpio: bool
    firma: str | None = None


class AntivirusNoDisponible(Exception):
    pass


class VirusScanner(Protocol):
    async def escanear(self, ruta: Path) -> ResultadoEscaneo: ...


class NoopScanner:
    """Solo desarrollo: no escanea. Nunca usar en producción."""

    async def escanear(self, ruta: Path) -> ResultadoEscaneo:
        log.warning("Antivirus deshabilitado (ANTIVIRUS_BACKEND=noop): %s sin escanear", ruta.name)
        return ResultadoEscaneo(limpio=True)


class ClamavScanner:
    def __init__(self, host: str, port: int, timeout_s: float):
        self.host, self.port, self.timeout_s = host, port, timeout_s

    async def escanear(self, ruta: Path) -> ResultadoEscaneo:
        try:
            return await asyncio.wait_for(self._escanear(ruta), self.timeout_s)
        except (OSError, TimeoutError) as exc:
            raise AntivirusNoDisponible(f"clamd no responde: {exc}") from exc

    async def _escanear(self, ruta: Path) -> ResultadoEscaneo:
        reader, writer = await asyncio.open_connection(self.host, self.port)
        try:
            writer.write(b"zINSTREAM\0")
            with ruta.open("rb") as f:
                while bloque := f.read(_BLOQUE):
                    writer.write(struct.pack(">I", len(bloque)) + bloque)
                    await writer.drain()
            writer.write(struct.pack(">I", 0))
            await writer.drain()
            respuesta = (await reader.read(4096)).rstrip(b"\0\n").decode("utf-8", "replace")
        finally:
            writer.close()
            await writer.wait_closed()

        if respuesta.endswith("OK"):
            return ResultadoEscaneo(limpio=True)
        if respuesta.endswith("FOUND"):
            firma = respuesta.removeprefix("stream:").removesuffix("FOUND").strip()
            return ResultadoEscaneo(limpio=False, firma=firma)
        # "INSTREAM size limit exceeded", errores de clamd, etc.: no se acepta el archivo.
        raise AntivirusNoDisponible(f"Respuesta inesperada de clamd: {respuesta!r}")


def get_scanner() -> VirusScanner:
    s = get_settings()
    if s.antivirus_backend == "noop":
        return NoopScanner()
    return ClamavScanner(s.clamav_host, s.clamav_port, s.clamav_timeout_s)
