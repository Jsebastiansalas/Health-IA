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

## Modelo de autorización
- Cada usuario pertenece a un tenant; todas las consultas filtran por `tenant_id`.
- `ADMIN_TENANT` administra usuarios, la política de borrado y todos los expedientes del tenant.
- Los demás roles acceden a un expediente solo con permiso explícito (`LECTOR` < `EDITOR` < `ADMIN`).
- Un expediente ajeno o sin permiso responde `404` (no revela que existe); un permiso insuficiente responde `403`.
