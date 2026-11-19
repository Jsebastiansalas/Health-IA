# MedTender RAG

Gestor inteligente de licitaciones médicas y auditoría en salud. Los PDF originales se quedan en el equipo del cliente; el servidor guarda solo fragmentos, embeddings (pgvector) y metadatos.

- Plan y sprints: [PLAN.md](PLAN.md)
- Requerimientos originales: [CONTEXTO_COMPLETO_PROYECTO_CLAUDE.md](CONTEXTO_COMPLETO_PROYECTO_CLAUDE.md)

## Estructura
```
backend/   FastAPI + SQLAlchemy + Alembic (Python 3.12, gestionado con uv)
infra/     docker-compose (PostgreSQL 16 + pgvector, Redis, ClamAV, Ollama)
frontend/  React + Vite (Sprint 5)
```

## Levantar en local
```powershell
cd backend
copy .env.example .env          # y cambia JWT_SECRET
uv sync

cd ..\infra
docker compose up -d --build postgres redis api
# API:     http://localhost:8010/docs
# Health:  http://localhost:8010/health
```
Puertos en el host (configurables): Postgres `5434`, Redis `6380`, API `8010`. ClamAV se levanta con `docker compose up -d clamav` (la primera descarga de firmas tarda varios minutos). Ollama: `docker compose --profile local up -d ollama`.

Desarrollo sin Docker para la API:
```powershell
cd infra; docker compose up -d postgres
cd ..\backend; uv run alembic upgrade head; uv run uvicorn app.main:app --reload
```

## Pruebas
Requieren Docker en ejecución (Testcontainers levanta un PostgreSQL + pgvector desechable):
```powershell
cd backend
uv run pytest
uv run ruff check .
```

## Ingesta efímera de PDFs
`POST /api/v1/expedientes/{id}/documentos` (multipart: `archivo`, `tipo_documento`, `numero_adenda`), requiere permiso `EDITOR`.

1. El PDF se recibe **en streaming** directo al directorio efímero (`{documento_id}.part`), calculando el SHA-256 y cortando en cuanto supera `MAX_UPLOAD_MB`. No pasa por el temporal del sistema.
2. Se rechaza al instante si no tiene firma `%PDF-` (422) o si ya existe en el expediente (409).
3. La API responde **202 con estado `VALIDANDO`**. En segundo plano corren el antivirus (ClamAV, protocolo INSTREAM) y la validación estructural (contraseña de apertura, PDF corrupto). Un pliego de 150 MB puede tardar cerca de un minuto en el antivirus.
4. El progreso se consulta con `GET .../documentos/{id}` (`estado_indexacion`, `progreso`, `motivo_error`, `actas_purga`).

Estados: `RECIBIDO → VALIDANDO → EN_COLA → EXTRAYENDO_OCR → FRAGMENTANDO → VECTORIZANDO → [INDEXADO_PENDIENTE_PURGA] → INDEXADO_Y_PURGADO`, o `ERROR_PURGADO` desde cualquier estado no final.

**Purga garantizada.** Antes de dar por indexado un documento se verifica en PostgreSQL que `COUNT(fragmentos con embedding) == total_chunks_esperados > 0`. Cada borrado (éxito, error, timeout, huérfano o eliminación manual) deja una fila en `actas_purga` con el SHA-256. Un barrido periódico purga las diferidas vencidas (`DIFERIDO_1H`), los documentos atascados y los archivos huérfanos.

## Modelo de autorización
- Cada usuario pertenece a un tenant; todas las consultas filtran por `tenant_id`.
- `ADMIN_TENANT` administra usuarios, la política de borrado y todos los expedientes del tenant.
- Los demás roles acceden a un expediente solo con permiso explícito (`LECTOR` < `EDITOR` < `ADMIN`).
- Un expediente ajeno o sin permiso responde `404` (no revela que existe); un permiso insuficiente responde `403`.
