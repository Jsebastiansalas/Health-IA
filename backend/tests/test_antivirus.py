"""Protocolo INSTREAM de clamd contra un servidor clamd simulado."""

import asyncio
import struct

import pytest

from app.services.antivirus import AntivirusNoDisponible, ClamavScanner
from tests.pdfs import MARCADOR_VIRUS


class ClamdFalso:
    def __init__(self, respuesta_forzada: bytes | None = None, max_bytes: int = 10_000_000):
        self.respuesta_forzada = respuesta_forzada
        self.max_bytes = max_bytes
        self.recibido = b""
        self.comando = b""

    async def manejar(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.comando = await reader.readuntil(b"\0")
        while True:
            (n,) = struct.unpack(">I", await reader.readexactly(4))
            if n == 0:
                break
            self.recibido += await reader.readexactly(n)
        if self.respuesta_forzada:
            respuesta = self.respuesta_forzada
        elif len(self.recibido) > self.max_bytes:
            respuesta = b"INSTREAM size limit exceeded. ERROR"
        elif MARCADOR_VIRUS in self.recibido:
            respuesta = b"stream: Win.Test.Marcador FOUND"
        else:
            respuesta = b"stream: OK"
        writer.write(respuesta + b"\0")
        await writer.drain()
        writer.close()


@pytest.fixture
async def clamd():
    falso = ClamdFalso()
    server = await asyncio.start_server(falso.manejar, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    yield falso, ClamavScanner("127.0.0.1", port, timeout_s=5)
    server.close()
    await server.wait_closed()


async def test_archivo_limpio(clamd, tmp_path):
    falso, scanner = clamd
    ruta = tmp_path / "a.pdf"
    contenido = b"%PDF-1.7" + b"x" * 200_000  # varios bloques de 64 KB
    ruta.write_bytes(contenido)

    resultado = await scanner.escanear(ruta)

    assert resultado.limpio and resultado.firma is None
    assert falso.comando == b"zINSTREAM\0"
    assert falso.recibido == contenido


async def test_virus_detectado(clamd, tmp_path):
    _, scanner = clamd
    ruta = tmp_path / "v.pdf"
    ruta.write_bytes(b"%PDF-1.7" + MARCADOR_VIRUS)
    resultado = await scanner.escanear(ruta)
    assert not resultado.limpio
    assert resultado.firma == "Win.Test.Marcador"


async def test_limite_de_clamd_no_se_acepta_como_limpio(clamd, tmp_path):
    falso, scanner = clamd
    falso.max_bytes = 10
    ruta = tmp_path / "g.pdf"
    ruta.write_bytes(b"%PDF-1.7" + b"x" * 100)
    with pytest.raises(AntivirusNoDisponible, match="size limit"):
        await scanner.escanear(ruta)


async def test_clamd_apagado(tmp_path):
    ruta = tmp_path / "a.pdf"
    ruta.write_bytes(b"%PDF-1.7")
    scanner = ClamavScanner("127.0.0.1", 1, timeout_s=2)
    with pytest.raises(AntivirusNoDisponible):
        await scanner.escanear(ruta)
