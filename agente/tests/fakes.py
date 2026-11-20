"""Dobles de prueba y utilidades compartidas."""

import uuid
from pathlib import Path


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


class Respuesta:
    """Lo mínimo de una respuesta HTTP que consumen las pruebas."""

    def __init__(self, status_code: int, cuerpo: dict):
        self.status_code = status_code
        self._cuerpo = cuerpo

    def json(self) -> dict:
        return self._cuerpo


async def subir(
    expediente_id: str,
    contenido: bytes,
    tipo: str = "PLIEGO",
    numero_adenda: int | None = None,
    nombre: str = "Pliego_Hospital.pdf",
) -> Respuesta:
    """Hace lo que la API Java deja listo antes de entregar un documento al agente: el PDF en el
    directorio efímero como {id}.pdf y la fila del documento en estado EN_COLA."""
    import hashlib
    import io
    import os

    import psycopg
    from pypdf import PdfReader

    doc_id = uuid.uuid4()
    try:
        paginas = len(PdfReader(io.BytesIO(contenido)).pages)
    except Exception:
        paginas = None
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    with psycopg.connect(url) as conn:
        fila = conn.execute(
            "INSERT INTO documentos (id, tenant_id, expediente_id, nombre_archivo_original, "
            "tipo_documento, numero_adenda, sha256_original, tamano_bytes, total_paginas, "
            "estado_indexacion, embedding_model) "
            "SELECT %s, e.tenant_id, e.id, %s, %s, %s, %s, %s, %s, 'EN_COLA', "
            "e.embedding_model_activo FROM expedientes e WHERE e.id = %s RETURNING tenant_id",
            (
                doc_id,
                nombre,
                tipo,
                numero_adenda or 0,
                hashlib.sha256(contenido).hexdigest(),
                len(contenido),
                paginas,
                uuid.UUID(expediente_id),
            ),
        ).fetchone()
    assert fila is not None, "expediente inexistente"
    (Path(os.environ["EPHEMERAL_DIR"]) / f"{doc_id}.pdf").write_bytes(contenido)
    return Respuesta(
        202, {"id": str(doc_id), "estado_indexacion": "EN_COLA", "tenant_id": str(fila[0])}
    )


def archivos(ephemeral_dir: Path) -> list[str]:
    return sorted(p.name for p in ephemeral_dir.iterdir())
