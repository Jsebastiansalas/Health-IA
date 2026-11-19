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
    # Máximo por proceso = pool_size + max_overflow (API y worker suman contra max_connections).
    db_pool_size: int = 15
    db_max_overflow: int = 15
    db_pool_timeout_s: float = 10.0

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

    # Versión de OCR vigente; documentos con OCR de otra versión muestran aviso (HU4.5).
    ocr_version_actual: str = "tesseract-5.5-v1"

    # ---------- Embeddings (Sprint 4) ----------
    # Modelo con el que nace cada expediente nuevo.
    embedding_model_default: str = "gemini-embedding-001"
    embedding_lote: int = 100  # textos por llamada al proveedor
    embedding_reintentos: int = 6
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    ollama_url: str = "http://localhost:11434"

    # ---------- Motor RAG (Sprint 5) ----------
    # gemini-2.5-flash: estable y ~2 s por respuesta en las pruebas. gemini-3.8-flash respondió
    # 503 por alta demanda o se colgó hasta el timeout, así que queda como respaldo.
    llm_model: str = "gemini-2.5-flash"
    # Se usan en orden si el principal responde 429/503 o no contesta a tiempo.
    llm_modelos_respaldo: list[str] = ["gemini-3.8-flash"]
    llm_temperatura: float = 0.1
    # Un modelo que se cuelga no se reintenta: se pasa al respaldo tras este plazo.
    llm_timeout_s: float = 30.0
    llm_intentos_por_modelo: int = 1
    rag_top_k: int = 20  # Top-K vectorial y Top-K léxico que entran a la fusión
    rag_rrf_k: int = 60  # constante k de Reciprocal Rank Fusion
    rag_max_evidencias: int = 6  # fragmentos principales enviados al modelo
    rag_boost_adenda: float = 0.25  # +25 % al puntaje de fragmentos de adendas
    rag_hnsw_ef_search: int = 100
    # strict_order: orden exacto por distancia (necesario para RRF). Ver app/rag/busqueda.py.
    rag_hnsw_iterative: Literal["strict_order", "relaxed_order"] = "strict_order"
    # Por debajo de esta confianza OCR la cita exige mirar el PDF original.
    umbral_confianza_ocr: float = 0.85

    # ---------- Operación y endurecimiento (Sprint 6) ----------
    entorno: Literal["desarrollo", "produccion"] = "desarrollo"
    log_json: bool = False  # en producción siempre JSON
    # Detrás de Caddy, la IP real del cliente es la última entrada de X-Forwarded-For.
    confiar_proxy: bool = False
    # /metrics: con token requiere `Authorization: Bearer <token>`; sin token y en producción
    # el endpoint no existe.
    metrics_token: str = ""

    rate_limit_habilitado: bool = True
    rate_limit_backend: Literal["redis", "memoria"] = "redis"
    rl_general_ip_min: int = 600  # todas las rutas, por IP
    rl_login_ip_min: int = 20  # intentos de login por IP
    rl_login_fallos_par: int = 5  # fallos por (IP, correo) antes de bloquear
    rl_login_fallos_ventana_s: int = 900
    rl_registro_ip_hora: int = 5
    rl_refresh_ip_min: int = 60
    rl_consulta_usuario_min: int = 20  # cada pregunta cuesta una llamada al LLM
    rl_consulta_usuario_dia: int = 500
    rl_subida_usuario_hora: int = 60
    rl_reindex_usuario_hora: int = 6

    def problemas_produccion(self) -> tuple[list[str], list[str]]:
        """(fatales, advertencias) de una configuración destinada a producción."""
        fatales: list[str] = []
        avisos: list[str] = []
        if "cambia-esto" in self.jwt_secret or len(set(self.jwt_secret)) < 10:
            fatales.append("JWT_SECRET es el valor de ejemplo o demasiado simple")
        if self.antivirus_backend == "noop":
            fatales.append("ANTIVIRUS_BACKEND=noop: en producción todo PDF debe escanearse")
        if "medtender:medtender@" in self.database_url:
            fatales.append("DATABASE_URL usa la contraseña de desarrollo 'medtender'")
        if self.cola_backend != "arq":
            fatales.append("COLA_BACKEND debe ser 'arq' para que los documentos se procesen")
        if self.rate_limit_habilitado and self.rate_limit_backend == "memoria":
            avisos.append("RATE_LIMIT_BACKEND=memoria no se comparte entre procesos")
        if not self.rate_limit_habilitado:
            avisos.append("RATE_LIMIT_HABILITADO=false: sin protección contra fuerza bruta")
        if self.allow_tenant_signup:
            avisos.append("ALLOW_TENANT_SIGNUP=true: cualquiera puede crear una organización")
        if any("localhost" in o or "127.0.0.1" in o for o in self.cors_origins):
            avisos.append("CORS_ORIGINS incluye localhost")
        if not self.confiar_proxy:
            avisos.append("CONFIAR_PROXY=false: el límite por IP verá la IP del proxy")
        if not self.gemini_api_key and not self.openai_api_key:
            avisos.append("Sin API key de embeddings: no se podrán vectorizar documentos")
        if not self.metrics_token:
            avisos.append("METRICS_TOKEN vacío: /metrics queda deshabilitado")
        return fatales, avisos

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
