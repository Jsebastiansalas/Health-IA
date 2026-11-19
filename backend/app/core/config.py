import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "MedTender RAG"
    database_url: str = "postgresql+asyncpg://medtender:medtender@localhost:5434/medtender"
    # NullPool evita compartir conexiones entre event loops (útil en tests).
    db_null_pool: bool = False

    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7

    allow_tenant_signup: bool = True
    cors_origins: list[str] = ["http://localhost:5173"]

    # ---------- Ingesta efímera (Sprint 2) ----------
    max_upload_mb: int = 300
    ephemeral_dir: Path = Path(tempfile.gettempdir()) / "medtender-ephemeral"

    # "noop" solo para desarrollo: no escanea y lo registra en el log.
    antivirus_backend: Literal["clamav", "noop"] = "clamav"
    clamav_host: str = "localhost"
    clamav_port: int = 3310
    clamav_timeout_s: float = 120.0

    # Política DIFERIDO_1H: minutos que se conserva el temporal tras indexar.
    purga_diferida_minutos: int = 60
    # Un documento que no termina en este plazo se marca como error y se purga.
    procesamiento_timeout_minutos: int = 360
    # Archivos del directorio efímero sin documento activo se borran tras este plazo.
    huerfano_minutos: int = 10
    barrido_habilitado: bool = True
    barrido_intervalo_s: int = 300

    # ---------- Procesamiento asíncrono (Sprint 3) ----------
    redis_url: str = "redis://localhost:6380/0"
    # "ninguna" deja los documentos en EN_COLA (útil si no hay Redis en desarrollo).
    cola_backend: Literal["arq", "ninguna"] = "arq"
    worker_max_jobs: int = 4
    worker_job_timeout_s: int = 3 * 3600
    # Procesos dedicados a extracción/OCR (pdfium no es seguro entre hilos).
    extraccion_procesos: int = 2

    # Extracción (Paso 5)
    umbral_texto_nativo: int = 60  # caracteres para considerar la página como nativa
    ocr_dpi: int = 300
    ocr_idioma: str = "spa"
    # Fracción del área de la página: imagen "relevante" y página "escaneada".
    imagen_relevante_min_area: float = 0.01
    imagen_escaneo_min_area: float = 0.30
    # Imágenes relevantes por debajo de este tamaño se consideran posibles sellos/firmas.
    imagen_sello_max_area: float = 0.15

    # Fragmentación (Paso 6)
    chunk_min_tokens: int = 500
    chunk_max_tokens: int = 1000
    chunk_overlap_ratio: float = 0.15

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
