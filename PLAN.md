# Plan de desarrollo — MedTender RAG (100 % Python + FastAPI)

## Contexto
Plataforma multi-tenant para licitaciones médicas y auditoría en salud. El usuario conserva los PDF en su PC; el VPS guarda solo fragmentos, embeddings (pgvector) y metadatos. El PDF se elimina tras indexar (con verificación) y las consultas RAG funcionan con el PC apagado. Directorio vacío: proyecto desde cero.

**Decisión del usuario:** todo el backend en Python con FastAPI, incluido el agente de IA. Reemplaza el Spring Boot del documento original (el requisito funcional se mantiene: autenticación, autorización, recepción y gestión de expedientes). Equivalencias:
| Documento original | Implementación Python |
|---|---|
| Spring Security + JWT | FastAPI + `pyjwt` + `passlib[bcrypt]`, dependencias de autorización |
| Spring Data JPA / Flyway | SQLAlchemy 2 + Alembic (migración inicial = esquema SQL del documento) |
| Spring AI `EmbeddingModel`/`ChatClient`/`PgVectorStore` | SDK `openai` + `pgvector-python` + SQL propio |
| `@Async` | Tareas en segundo plano con cola (ARQ + Redis, o Celery) |
| Tika | `python-magic` / verificación `%PDF-` + `pikepdf` (detecta cifrado) |
| PDFBox / Tabula / Tess4J / JTokkit | PyMuPDF / pdfplumber / pytesseract / tiktoken |

## Arquitectura
```
React (Vite/TS) ──HTTPS──> FastAPI (api)  ──encola──> Worker Python (ARQ)
                              │ auth, tenants, permisos,          │ extracción, OCR, chunking,
                              │ expedientes, ingesta, RAG         │ embeddings, purga
                              └────────── PostgreSQL 16 + pgvector + Redis ─────┘
```
Un mismo código base (`app/`) con dos procesos: API y worker. Todas las consultas filtran por `tenant_id` y `expediente_id` desde una capa de repositorio única.

## Decisiones técnicas / riesgos
1. Python 3.12 con `uv` (evitar 3.14 por wheels).
2. `vector(1536)` fijo; `bge-m3` es de 1024 dims → columna/tabla adicional en la migración local (Sprint 4).
3. Un único enum de estados compartido entre BD y UI.
4. Tesseract con `spa.traineddata` en Docker y en tu Windows para pruebas.
5. File System Access API: solo Chrome/Edge sobre HTTPS/localhost.
6. Redis añade un servicio; alternativa mínima: cola en tabla de PostgreSQL (`SELECT ... FOR UPDATE SKIP LOCKED`) para el MVP.
7. Antivirus: ClamAV (`clamd` por socket TCP) con interfaz enchufable y fallback en desarrollo.

## Stack
| Capa | Tecnología |
|---|---|
| Lenguajes | Python 3.12, TypeScript, SQL |
| API | FastAPI, Uvicorn, Pydantic v2, pydantic-settings |
| Datos | PostgreSQL 16 + pgvector (HNSW) + GIN `tsvector('spanish')`, SQLAlchemy 2 (async), Alembic, psycopg 3 |
| Cola | ARQ + Redis (o tabla en Postgres) |
| Seguridad | pyjwt, passlib/bcrypt, clamd, slowapi (rate limit) |
| PDF | PyMuPDF, pdfplumber (tablas → Markdown), pytesseract, pikepdf |
| Chunking | tiktoken (cl100k_base), 500–1000 tokens, 15 % overlap |
| IA | SDK `openai` (`text-embedding-3-small`, `gpt-4o-mini`/`gpt-4o`), Ollama `bge-m3` vía `EmbeddingRouter`, LangGraph para el agente, salida estructurada con Pydantic |
| Frontend | React + Vite + TS + Tailwind, `pdfjs-dist`, TanStack Query |
| Calidad | ruff, mypy, pytest, pytest-asyncio, testcontainers-python, respx, RAGAS; Vitest; Playwright |
| Infra | Docker Compose (postgres, redis, clamav, ollama, api, worker), GitHub Actions |

## Sprints e historias de usuario

### Sprint 1 — Infraestructura, seguridad multi-tenant y expedientes
- HU1.1 `docker-compose up` levanta postgres (pgvector pg16), redis, clamav y api.
- HU1.2 Migración Alembic inicial con tablas e índices del documento (HNSW, GIN).
- HU1.3 Login JWT con `tenant_id` y rol; tokens de corta duración + refresh.
- HU1.4 ADMIN_TENANT gestiona usuarios y roles (ADMIN_TENANT, JURIDICO, AUDITOR_MEDICO, BIOMEDICO, LECTOR).
- HU1.5 CRUD de expedientes y permisos LECTOR/EDITOR/ADMIN.
- HU1.6 Tests de aislamiento entre tenants y de permisos.

### Sprint 2 — Ingesta efímera, validación, SHA-256 y purga
- HU2.1 `POST /api/v1/expedientes/{id}/documentos` con límite de tamaño, `tipo_documento`, `numero_adenda`.
- HU2.2 Validación: firma `%PDF-`, no cifrado, antivirus (interfaz `VirusScanner`).
- HU2.3 SHA-256 en streaming, guardado temporal aislado (`/tmp/medtender-ephemeral/{uuid}.pdf`), duplicados por hash.
- HU2.4 Máquina de estados persistida y consultable (`GET .../estado`, SSE opcional).
- HU2.5 Purga: verificar `COUNT(embedding)==total_chunks_esperados`, borrado en `finally`, Acta de Purga, barrido programado de huérfanos, política INMEDIATO/DIFERIDO_1H.

### Sprint 3 — Extracción, OCR, tablas y chunking
- HU3.1 Worker consume el trabajo y actualiza estados.
- HU3.2 Extracción página a página con PyMuPDF (umbral 60 caracteres).
- HU3.3 Tablas a Markdown.
- HU3.4 OCR selectivo a 300 DPI con `ocr_confidence`.
- HU3.5 Detección de sellos/firmas/imágenes en `metadata_jsonb`.
- HU3.6 Chunking con tiktoken, detección de encabezados (CAPÍTULO, CLÁUSULA, ADENDA…), página/sección/orden.
- HU3.7 Reintentos y manejo de errores → `ERROR_PURGADO`.

### Sprint 4 — Vectorización y EmbeddingRouter
- HU4.1 Cabecera contextual en `contenido_vectorizado`.
- HU4.2 Embeddings por lotes con backoff (tenacity) y persistencia en pgvector.
- HU4.3 `EmbeddingRouter` según `embedding_model_activo` del expediente.
- HU4.4 Re-vectorización desde texto, sin PDF, hacia Ollama/`bge-m3`.
- HU4.5 Aviso de `ocr_version` antigua en la UI.

### Sprint 5 — Agente RAG y frontend con visor local
- HU5.1 `POST /api/v1/expedientes/{id}/consultas` con permiso y filtro de tenant obligatorios.
- HU5.2 SQL híbrida RRF (Top 20 vectorial + Top 20 `ts_rank_cd` con `websearch_to_tsquery('spanish')`).
- HU5.3 Expansión por `orden±1` y boost de ADENDA con alerta de modificación.
- HU5.4 Agente LangGraph con herramientas (buscar, expandir contexto, revisar adendas) y salida estructurada con citas; abstención sin evidencia; validación de que cada cita proviene de un fragmento recuperado.
- HU5.5 Frontend: login, expedientes, subida con progreso, chat con citas clicables y alertas probatorias.
- HU5.6 Visor local: `showDirectoryPicker`, SHA-256 con Web Crypto, comparación con `sha256Original`, PDF.js en la página citada sin subir el archivo.
- HU5.7 Evaluación RAG: set dorado, recall@k, abstención correcta.

### Sprint 6 — Endurecimiento
Observabilidad (logs estructurados, métricas), rate limiting, auditoría de accesos, backups, despliegue en VPS con HTTPS (Caddy), pruebas de carga.

## MCPs, skills y plugins
**Ya disponibles (usaré):** `impeccable` y `frontend-design` (UI), `anthropic-skills:pdf` (PDFs de prueba), `claude-api` (si se usa Claude como LLM alternativo), `code-review`, `security-review`, `simplify`, `run`, `claude-in-chrome` (probar el visor local), `init`, `update-config`.
**MCPs a agregar:** PostgreSQL MCP (esquema y EXPLAIN de la consulta RRF), GitHub MCP, Context7 (docs al día de FastAPI, PyMuPDF, LangGraph, SQLAlchemy), Playwright MCP; opcional Docker MCP.
**Herramientas tuyas:** Python 3.12 + `uv`, Tesseract con paquete `spa`, Docker Desktop, VS Code con extensiones Python/Ruff.
**Necesito de ti:** `git init`, API key de OpenAI (variable de entorno), 3–5 PDFs de ejemplo anonimizados.

## Verificación
- pytest con Postgres real (testcontainers) y OpenAI simulado con respx.
- PDFs de muestra: nativo, escaneado, mixto y con tablas.
- Seguridad: aislamiento de tenants/permisos; ningún PDF queda en el directorio efímero.
- E2E con Playwright (subir → indexar → preguntar → citar → abrir PDF local).
- Calidad RAG con set dorado antes de cerrar Sprint 5.

## Primer paso al aprobar
`git init`, estructura monorepo (`backend/`, `frontend/`, `infra/`), `pyproject.toml` (uv), `docker-compose.yml` y migración Alembic inicial (Sprint 1).
