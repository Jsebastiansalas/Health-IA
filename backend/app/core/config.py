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

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
