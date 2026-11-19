"""Dobles de prueba y utilidades compartidas."""

import uuid
from pathlib import Path

from httpx import AsyncClient

from app.services.antivirus import AntivirusNoDisponible, ResultadoEscaneo
from tests.pdfs import MARCADOR_VIRUS


class ScannerFalso:
    def __init__(self, caido: bool = False):
        self.caido = caido
        self.escaneados: list[str] = []

    async def escanear(self, ruta: Path) -> ResultadoEscaneo:
        self.escaneados.append(ruta.name)
        if self.caido:
            raise AntivirusNoDisponible("conexión rechazada")
        if MARCADOR_VIRUS in ruta.read_bytes():
            return ResultadoEscaneo(limpio=False, firma="Test.Marcador")
        return ResultadoEscaneo(limpio=True)


class ColaFalsa:
    def __init__(self, falla: bool = False):
        self.falla = falla
        self.encolados: list[uuid.UUID] = []

    async def encolar(self, documento_id: uuid.UUID) -> None:
        if self.falla:
            raise RuntimeError("redis caído")
        self.encolados.append(documento_id)


async def subir(
    client: AsyncClient,
    headers: dict,
    expediente_id: str,
    contenido: bytes,
    tipo: str = "PLIEGO",
    numero_adenda: int | None = None,
    nombre: str = "Pliego_Hospital.pdf",
):
    data = {"tipo_documento": tipo}
    if numero_adenda is not None:
        data["numero_adenda"] = str(numero_adenda)
    return await client.post(
        f"/api/v1/expedientes/{expediente_id}/documentos",
        headers=headers,
        data=data,
        files={"archivo": (nombre, contenido, "application/pdf")},
    )


def archivos(ephemeral_dir: Path) -> list[str]:
    return sorted(p.name for p in ephemeral_dir.iterdir())
