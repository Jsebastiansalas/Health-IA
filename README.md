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

## Procesamiento asíncrono (worker)
`docker compose up -d worker` arranca `arq app.worker.WorkerSettings`. Consume la cola de Redis y ejecuta cada 5 minutos el barrido de purga.

- **Extracción página a página** (`app/pipeline/extraccion.py`), en procesos separados porque pdfium no es seguro entre hilos:
  - Texto nativo con pypdfium2.
  - Tablas con bordes detectadas por pdfplumber y convertidas a Markdown, intercaladas en orden de lectura.
  - OCR con Tesseract (`spa`, 300 DPI) **solo** en páginas con menos de 60 caracteres nativos y una imagen que cubre al menos el 30 % de la página.
  - Las imágenes relevantes marcan `has_visual_elements`. Las de tamaño de sello o firma, o las páginas con vocabulario de firma, notaría o sello, marcan `has_signatures_or_stamps`.
- **Fragmentación** (`app/pipeline/fragmentacion.py`): 500–1.000 tokens reales `cl100k_base` con un solape de ~15 %. Detecta encabezados (CAPÍTULO, CLÁUSULA, ADENDA, NUMERAL, SECCIÓN, FICHA TÉCNICA, ANTECEDENTES, ANEXO, ARTÍCULO). Las tablas grandes se parten repitiendo la fila de encabezado.
- Los fragmentos se guardan con su **cabecera contextual** y `embedding = NULL`; el Sprint 4 los vectoriza.

Librerías PDF con licencias permisivas (pypdfium2: Apache/BSD; pdfplumber: MIT). Se evitó PyMuPDF por su licencia AGPL.

## Embeddings y EmbeddingRouter
`app/ia/embeddings.py` traduce el nombre de modelo de cada expediente (`embedding_model_activo`) a su proveedor. Los documentos y las preguntas siempre se vectorizan con el **mismo** modelo del índice consultado.

| Modelo | Proveedor | Dimensión |
|---|---|---|
| `gemini-embedding-001` (por defecto) | Google AI Studio, `outputDimensionality=1536`, normalizado | 1536 |
| `text-embedding-3-small` | OpenAI | 1536 |
| `bge-m3` | Ollama local (`docker compose --profile local up -d ollama` y luego `docker compose exec ollama ollama pull bge-m3`) | 1024 |

Los vectores de menor dimensión se rellenan con ceros hasta 1536. La similitud coseno no cambia, así que todo usa la misma columna y el mismo índice HNSW.

**Vectorización:** al terminar la fragmentación, el worker vectoriza `contenido_vectorizado` por lotes con reintentos (429/5xx con backoff), verifica `COUNT == total_chunks_esperados` y purga el PDF según la política del tenant.

**Re-vectorización sin PDF:** `POST /api/v1/expedientes/{id}/reindexaciones {"embedding_model": "bge-m3"}` (permiso ADMIN).
- Recalcula los vectores desde el texto guardado en PostgreSQL, en una tabla de preparación.
- Los intercambia en **una sola transacción**: el expediente sigue consultable durante el proceso y, si algo falla, el índice original queda intacto.
- Mientras dura, no se aceptan subidas al expediente.

**Aviso de OCR:** `aviso_ocr_desactualizado` en cada documento indica que tuvo páginas OCR con una versión distinta a `OCR_VERSION_ACTUAL`. Conviene volver a cargar ese PDF desde el PC.

## Motor RAG (consultas)
`POST /api/v1/expedientes/{id}/consultas {"pregunta": "..."}` requiere permiso LECTOR. `GET` sobre la misma ruta devuelve el historial propio.

1. **Paso 11:** la pregunta se vectoriza con el `embedding_model_activo` del expediente.
2. **Paso 12:** una sola consulta SQL filtra **siempre** por tenant, expediente, modelo y documentos indexados. Combina el Top-20 vectorial (pgvector con `hnsw.iterative_scan`) y el Top-20 léxico (`ts_rank_cd`, español) mediante **Reciprocal Rank Fusion**. La rama léxica usa un OR de los lexemas de la pregunta: `websearch_to_tsquery` exige todas las palabras y no sirve para lenguaje natural. Los códigos CUM, UNSPSC e INVIMA coinciden exactos.
3. **Paso 13:** boost de +25 % a las adendas (gana la de mayor número) y expansión con los vecinos `orden±1`.
4. **Paso 14:** Gemini (`LLM_MODEL`, con `LLM_MODELOS_RESPALDO` si está saturado) responde en JSON estructurado. Las citas se arman desde PostgreSQL:
   - el modelo solo elige ids de fragmento;
   - los ids inexistentes se descartan;
   - los extractos que no son literales se reemplazan por el texto real.
   - Sin evidencia, la respuesta es una abstención explícita.
   - Cada cita indica si requiere verificar el PDF original: sellos o firmas, tablas, imágenes u OCR de baja confianza.

## Frontend web
```powershell
cd frontend
npm install
npm run dev      # http://localhost:5173  (proxy /api -> http://localhost:8010)
npm test         # Vitest
npm run build    # tipado estricto + build de producción en dist/
```
- **Expedientes:** archivo con búsqueda y creación.
- **Folios:** carga con progreso real de bytes y línea de tiempo del pipeline, que termina en el sello *PDF eliminado* con la fecha de purga. Muestra también el motivo de rechazo y el aviso de OCR desactualizado.
- **Consulta:** chat RAG con citas en tarjetas (documento, página, sección, extracto literal, método y confianza OCR), el sello *Verificar original* y alertas de adendas. Las sugerencias rellenan la pregunta.
- **Visor local desacoplado:** con "Vincular carpeta local de PDFs" (`showDirectoryPicker`, solo lectura y recordada en IndexedDB):
  1. busca el original por nombre y, si fue renombrado, por SHA-256;
  2. calcula la huella con `crypto.subtle.digest` y la compara con `sha256Original`;
  3. lo abre con PDF.js en la página donde está el extracto.

  **El archivo nunca se sube.** En navegadores sin File System Access (Firefox, Safari) se puede elegir el PDF a mano, con la misma verificación.
- **Fuentes:** empaquetadas localmente (`@fontsource`), sin CDN de terceros.

## Modelo de autorización
- Cada usuario pertenece a un tenant; todas las consultas filtran por `tenant_id`.
- `ADMIN_TENANT` administra usuarios, la política de borrado y todos los expedientes del tenant.
- Los demás roles acceden a un expediente solo con permiso explícito (`LECTOR` < `EDITOR` < `ADMIN`).
- Un expediente ajeno o sin permiso responde `404` (no revela que existe); un permiso insuficiente responde `403`.
