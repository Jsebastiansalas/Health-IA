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
        self.reindexaciones: list[uuid.UUID] = []

    async def encolar(self, documento_id: uuid.UUID) -> None:
        if self.falla:
            raise RuntimeError("redis caído")
        self.encolados.append(documento_id)

    async def encolar_reindexacion(self, reindexacion_id: uuid.UUID) -> None:
        self.reindexaciones.append(reindexacion_id)


class EmbeddingsFalsos:
    """Proveedor determinista: el mismo texto produce siempre el mismo vector normalizado."""

    def __init__(self, modelo: str, dimension: int, falla_en_llamada: int | None = None):
        self.modelo = modelo
        self.dimension = dimension
        self.falla_en_llamada = falla_en_llamada
        self.llamadas: list[tuple[str, int]] = []  # (tarea, cantidad de textos)

    async def embeber(self, textos: list[str], tarea: str) -> list[list[float]]:
        import hashlib
        import math

        self.llamadas.append((tarea, len(textos)))
        if self.falla_en_llamada is not None and len(self.llamadas) >= self.falla_en_llamada:
            raise RuntimeError(f"{self.modelo} no responde")
        vectores = []
        for t in textos:
            semilla = hashlib.sha256(t.encode()).digest()
            v = [((semilla[i % 32] + i * 7) % 255) / 255 - 0.5 for i in range(self.dimension)]
            n = math.sqrt(sum(x * x for x in v))
            vectores.append([x / n for x in v])
        return vectores


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
