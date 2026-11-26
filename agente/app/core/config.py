import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.privacidad.cifrado_columnas import CifradorDatos, ErrorCifrado


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

    # ---------- Servicio interno ----------
    # Este servicio NO autentica usuarios: la API pública (Spring Boot) lo hace y le habla por la
    # red interna con este secreto compartido en la cabecera X-Internal-Token. Sin él, todos los
    # endpoints /internal responden 503.
    internal_token: str = ""

    # Directorio compartido con la API Java: ella escribe el PDF, este servicio lo procesa y lo
    # borra (Acta de Purga).
    ephemeral_dir: Path = Path(tempfile.gettempdir()) / "medtender-ephemeral"

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

    # Fotos de documentos (sprint 26)
    imagen_confianza_minima: float = 0.45
    imagen_texto_minimo: int = 20

    # Fragmentación (Paso 6)
    chunk_min_tokens: int = 500
    chunk_max_tokens: int = 1000
    chunk_overlap_ratio: float = 0.15

    # Versión de OCR vigente; documentos con OCR de otra versión muestran aviso (HU4.5).
    ocr_version_actual: str = "tesseract-5.5-v1"

    # ---------- Embeddings (Sprint 4) ----------
    # Modelo con el que nacen los expedientes nuevos (lo aplica la API Java).
    embedding_model_default: str = "gemini-embedding-001"
    embedding_lote: int = 100  # textos por llamada al proveedor
    embedding_reintentos: int = 6
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    ollama_url: str = "http://localhost:11434"

    # ---------- Privacidad (Sprint 25) ----------
    # Enmascara nombres, cédulas, teléfonos, correos y direcciones ANTES de enviar texto a un
    # proveedor de IA externo (embeddings y LLM). Lo guardado y lo que se muestra es el original.
    anonimizar_antes_de_nube: bool = True

    # ---------- Motor RAG (Sprint 5) ----------
    # gemini-2.5-flash: estable y ~2 s por respuesta en las pruebas. gemini-3.8-flash respondió
    # 503 por alta demanda o se colgó hasta el timeout, así que queda como respaldo.
    # Comprueba al arrancar que los modelos configurados existen y responden (no impide arrancar).
    verificar_modelos_al_arrancar: bool = True
    llm_model: str = "gemini-2.5-flash"
    # Se usan en orden si el principal responde 429/503 o no contesta a tiempo.
    llm_modelos_respaldo: list[str] = ["gemini-3.8-flash"]
    llm_temperatura: float = 0.1
    # Un modelo que se cuelga no se reintenta: se pasa al respaldo tras este plazo.
    llm_timeout_s: float = 30.0
    llm_intentos_por_modelo: int = 1

    # ---------- Operación (Sprint 43) ----------
    # DSN de GlitchTip (o compatible con Sentry) para reportar errores sin datos de salud.
    # Vacío: apagado.
    errores_dsn: str = ""

    # ---------- Datos en reposo (Sprint 42) ----------
    # Clave (32 bytes en base64) con la que se cifran en la base las preguntas y respuestas. La API
    # Java necesita la misma. Vacía: se guardan sin cifrar (solo desarrollo).
    datos_clave: str = ""

    # ---------- IA de producción (Sprint 41) ----------
    # Por dónde llega Gemini (generación y embeddings de gemini-embedding-001):
    # - gemini_api: API de Google AI Studio con GEMINI_API_KEY. Su capa gratuita puede usar lo
    #   que recibe para mejorar los productos de Google: solo para desarrollo.
    # - vertex: Gemini en Google Cloud (Vertex AI) con una cuenta de servicio; los datos no se
    #   usan para entrenar. Es el único permitido con ENTORNO=produccion.
    ia_proveedor: Literal["gemini_api", "vertex"] = "gemini_api"
    vertex_proyecto: str = ""
    # Región del modelo generativo: «global», una multirregión («us», «eu») o una región. Cada
    # modelo se ofrece solo en algunas: gemini-3.8-flash está en global, us y eu, no en
    # us-central1. Con «global» Google decide dónde se procesa.
    vertex_region: str = "global"
    # Región de los embeddings, aparte porque no tienen las mismas que el modelo generativo. La
    # documentación de gemini-embedding-001 muestra us-central1.
    vertex_region_embeddings: str = "us-central1"
    # Ruta al JSON de la cuenta de servicio (rol «Agent Platform User», antes «Vertex AI User»).
    # Vacío: servidor de metadatos de Google Cloud, si el agente corre allí.
    vertex_credenciales: str = ""
    # Peticiones simultáneas de embeddings a Vertex (gemini-embedding-001 recibe un texto por
    # petición).
    vertex_embeddings_concurrencia: int = 8
    # Segundo proveedor, que responde si Gemini falla o se satura. Vacío = sin respaldo.
    llm_respaldo_proveedor: Literal["", "claude"] = ""
    anthropic_api_key: str = ""
    claude_modelo: str = "claude-opus-5-5"
    claude_esfuerzo: Literal["low", "medium", "high"] = "medium"
    # Cortacircuitos: tras N fallos seguidos de un proveedor, no se le envían llamadas durante
    # este tiempo (va directo al siguiente). Pasado el plazo se le da otra oportunidad.
    ia_cortacircuitos_fallos: int = 3
    ia_cortacircuitos_s: float = 120.0
    # Tope de gasto diario estimado del modelo generativo en dólares (0 = sin tope).
    ia_tope_diario_usd: float = 0.0
    # Precios propios por modelo, US$ por millón de tokens: {"modelo": [entrada, salida]}.
    ia_precios: dict[str, tuple[float, float]] = {}
    # «Explícame este documento»: tope de fragmentos que se envían al modelo (≈ 700 tokens c/u).
    explicar_max_fragmentos: int = 30
    # Línea de tiempo: el modelo lee cada documento una vez. Fragmentos por llamada (también el
    # tope de «Preparar mi cita»), tope por documento y llamadas simultáneas al abrir la línea.
    cronologia_max_fragmentos: int = 60
    cronologia_max_fragmentos_documento: int = 600
    cronologia_llamadas_paralelas: int = 3
    # Leer cada documento al indexarlo (cuentas personales). Con la dirección vacía, o si falla,
    # se lee la primera vez que se abre la línea. La usa solo el worker.
    cronologia_al_indexar: bool = True
    agente_url: str = ""
    agente_timeout_s: float = 300.0
    # Fichas técnicas de CIMA (AEMPS): apagadas por defecto hasta confirmar sus condiciones de
    # reutilización.
    # Sin ellas, la información de medicamentos sale de los prospectos que sube la persona.
    fichas_cima_activas: bool = False
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
    # Detrás de un proxy, la IP real del cliente es la última entrada de X-Forwarded-For.
    confiar_proxy: bool = False
    # /metrics: con token requiere `Authorization: Bearer <token>`; sin token y en producción
    # el endpoint no existe.
    metrics_token: str = ""

    @model_validator(mode="after")
    def _modelos_de_vertex(self):
        """Vertex y la API de AI Studio no retiran los modelos a la vez: en Vertex,
        gemini-2.5-flash salía el 20-oct-2026. Solo cambia lo que no se haya configurado."""
        if self.ia_proveedor == "vertex":
            configurado = set(self.model_fields_set)
            if "llm_model" not in configurado:
                self.llm_model = "gemini-3.8-flash"
            if "llm_modelos_respaldo" not in configurado:
                self.llm_modelos_respaldo = ["gemini-3.5-flash"]
        return self

    def problemas_produccion(self) -> tuple[list[str], list[str]]:
        """(fatales, advertencias) de una configuración destinada a producción."""
        fatales: list[str] = []
        avisos: list[str] = []
        if len(self.internal_token) < 32 or len(set(self.internal_token)) < 10:
            fatales.append("INTERNAL_TOKEN debe tener al menos 32 caracteres y no ser trivial")
        if "medtender:medtender@" in self.database_url:
            fatales.append("DATABASE_URL usa la contraseña de desarrollo 'medtender'")
        if self.cola_backend != "arq":
            fatales.append("COLA_BACKEND debe ser 'arq' para que los documentos se procesen")
        try:
            CifradorDatos(self.datos_clave)
        except ErrorCifrado:
            fatales.append(
                "DATOS_CLAVE debe ser de 32 bytes en base64: cifra el historial en la base"
            )
        if self.ia_proveedor == "gemini_api":
            fatales.append(
                "IA_PROVEEDOR=gemini_api: la API de Google AI Studio puede usar los datos para "
                "mejorar sus productos; en producción usa IA_PROVEEDOR=vertex"
            )
        elif not self.vertex_proyecto:
            fatales.append("IA_PROVEEDOR=vertex requiere VERTEX_PROYECTO")
        if self.ia_proveedor == "vertex" and self.llm_model.startswith("gemini-2.5"):
            avisos.append(
                f"LLM_MODEL={self.llm_model}: Google fijó su retiro de Vertex para el 20-oct-2026; "
                "usa gemini-3.8-flash"
            )
        if self.llm_respaldo_proveedor == "claude" and not self.anthropic_api_key:
            fatales.append("LLM_RESPALDO_PROVEEDOR=claude requiere ANTHROPIC_API_KEY")
        if not self.llm_respaldo_proveedor:
            avisos.append("Sin proveedor de respaldo: si Gemini falla, la IA no responde")
        if self.ia_tope_diario_usd <= 0:
            avisos.append("IA_TOPE_DIARIO_USD sin definir: el gasto en IA no tiene tope")
        if self.ia_proveedor == "gemini_api" and not (self.gemini_api_key or self.openai_api_key):
            avisos.append("Sin API key de embeddings: no se podrán vectorizar documentos")
        if not self.metrics_token:
            avisos.append("METRICS_TOKEN vacío: /metrics queda deshabilitado")
        return fatales, avisos


@lru_cache
def get_settings() -> Settings:
    return Settings()
