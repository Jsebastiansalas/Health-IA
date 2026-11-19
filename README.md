# MedTender RAG

Gestor inteligente de licitaciones médicas y auditoría en salud. Los PDF originales se quedan en el equipo del cliente; el servidor guarda solo fragmentos, embeddings (pgvector) y metadatos.

- Plan y sprints: [PLAN.md](PLAN.md)
- Requerimientos originales: [CONTEXTO_COMPLETO_PROYECTO_CLAUDE.md](CONTEXTO_COMPLETO_PROYECTO_CLAUDE.md)

## Estructura
```
backend/   FastAPI + SQLAlchemy + Alembic (Python 3.12, gestionado con uv)
infra/     docker-compose de desarrollo y de producción, respaldos, ClamAV
frontend/  React + Vite + TypeScript + Tailwind (y Caddyfile de producción)
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

## Operación y seguridad (Sprint 6)

### Observabilidad
- **Logs JSON** (`LOG_JSON=true`, siempre en producción): cada línea lleva `request_id`, `usuario_id` y `tenant_id`. El `X-Request-ID` se devuelve en cada respuesta (también en los 429) y permite seguir una petición de punta a punta. El log de acceso usa la **plantilla** de la ruta (`/expedientes/{expediente_id}`), nunca la URL con ids ni la query. No se registran cuerpos, contraseñas, tokens ni el texto de preguntas o documentos.
- **`GET /metrics`** (Prometheus; `Authorization: Bearer $METRICS_TOKEN`; en producción sin token no existe y Caddy no lo publica):
  - de la API: solicitudes y duración por ruta, rechazos 429, consultas por resultado y modelo, fallos del almacén de límites y de auditoría;
  - del negocio, calculadas desde PostgreSQL en cada lectura (reflejan también al worker): documentos por estado, atascados más de 1 h, PDF temporales sin purgar, actas de purga por motivo, fragmentos, reindexaciones y consultas en 24 h.
- **`GET /health`** comprueba PostgreSQL. El worker publica un latido (`arq --check`) que usa su healthcheck de Docker.

Alertas sugeridas: `medtender_documentos_en_proceso_mas_de_1h > 0`, `medtender_pdf_temporales_pendientes` creciendo sin que haya subidas, `rate(medtender_consultas_total{resultado="error_ia"}[5m]) > 0`, `medtender_auditoria_fallos_total` > 0 y el healthcheck del contenedor `backup`.

### Límites de peticiones
Ventana fija en Redis (`SET NX EX` + `INCR` en una transacción: la clave siempre expira). Si Redis cae, se permite la petición y se cuenta en `medtender_rate_limit_backend_errores_total`. Todos los valores son ajustables (`RL_*`):

| Regla | Por defecto |
|---|---|
| General, por IP (excepto `/health` y `/metrics`) | 600/min |
| Login, por IP | 20/min |
| Login, fallos por **par (IP, correo)** | 5 en 15 min, luego 429 |
| Registro de organizaciones, por IP | 5/hora |
| Consultas RAG, por usuario (cada una cuesta una llamada al LLM) | 20/min y 500/día |
| Subidas de PDF, por usuario (se rechaza antes de aceptar bytes) | 60/hora |
| Reindexaciones, por usuario | 6/hora |

El bloqueo del login es por **par IP+correo**: quien adivina contraseñas queda frenado, pero un tercero no puede dejar fuera al usuario legítimo desde otra IP. Detrás de Caddy (`CONFIAR_PROXY=true`) la IP real es la **última** entrada de `X-Forwarded-For`; sin proxy de confianza la cabecera se ignora para que no sirva para evadir el límite.

### Auditoría de accesos
Tabla `auditoria` de **solo anexado** (un trigger rechaza `UPDATE` y `DELETE`) y sin claves foráneas, de modo que sobrevive al borrado de expedientes y usuarios. Registra: inicios de sesión OK, fallidos y bloqueados; alta de organizaciones y usuarios; cambios de rol; expedientes y permisos; **accesos denegados** (incluidos los intentos entre tenants, que al cliente le devuelven 404 pero quedan registrados); subidas y eliminaciones de documentos con su SHA-256; consultas RAG (solo el id, el resultado y la latencia, **nunca el texto de la pregunta**) y reindexaciones.

`GET /api/v1/auditoria` (solo `ADMIN_TENANT`, siempre acotado a su tenant) con filtros `accion`, `resultado`, `usuario_id`, `recurso_id`, `desde`, `hasta`. Auditar es de mejor esfuerzo: si el registro falla, la petición no se cae, pero se incrementa `medtender_auditoria_fallos_total`.

### Respaldos
`infra/backup/backup.sh` hace `pg_dump` en formato custom, **verifica que la copia sea legible**, la **cifra con AES-256** (`BACKUP_PASSPHRASE`), guarda su SHA-256 y borra las más antiguas que `BACKUP_RETENCION_DIAS`. En producción lo ejecuta el servicio `backup` cada 24 h y su healthcheck falla si pasan más de 36 h sin una copia correcta.

Los respaldos **no contienen PDF** (el sistema no los conserva), pero sí el texto extraído: son información confidencial. Guarde la frase de cifrado en un gestor de secretos; **sin ella no se pueden restaurar**.

```bash
# Restaurar en una base NUEVA (nunca sobrescribe la de producción) y verificar el contenido:
docker compose -f docker-compose.prod.yml run --rm --no-deps -e BACKUP_PASSPHRASE=... \
    -e PGHOST=postgres -e PGUSER=medtender -e PGPASSWORD=... --entrypoint bash backup \
    /scripts/restore.sh /backups/medtender-20270101T030000Z.dump.enc medtender_restaurada
```
La restauración comprueba el hash, descifra, restaura, cuenta las filas de **todas** las tablas, confirma el índice HNSW y ejecuta una búsqueda vectorial real. Con `BASE_ORIGEN=medtender` compara además los conteos contra esa base. Pruebe una restauración **antes** de necesitarla.

### Producción (VPS con HTTPS)
`infra/docker-compose.prod.yml` publica solo Caddy (80/443, certificado automático de Let's Encrypt). Postgres, Redis y el respaldo viven en una red `internal` sin salida a internet; los contenedores de la aplicación corren sin privilegios (`cap_drop: ALL`, `no-new-privileges`, sistema de archivos de solo lectura). Las migraciones se aplican una sola vez en un servicio `migrar` antes de arrancar la API y el worker.

```bash
cd infra
cp .env.prod.example .env.prod          # completar secretos (python -c "import secrets; print(secrets.token_hex(32))")
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
# Primera organización (el registro público queda cerrado: ALLOW_TENANT_SIGNUP=false):
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm \
    -e MEDTENDER_ADMIN_PASSWORD='una-clave-larga' api \
    python -m app.cli crear-tenant --nombre "Hospital X" --nit 900123 --email admin@hospital.co
```
- **Arranque seguro:** con `ENTORNO=produccion` la API se niega a iniciar si el `JWT_SECRET` es el de ejemplo o débil, si el antivirus está en `noop`, si la contraseña de Postgres es la de desarrollo o si la cola está desactivada. `python -m app.cli verificar-config` muestra además las advertencias (registro abierto, CORS con localhost, sin API key...).
- **Cabeceras de Caddy:** HSTS, CSP estricta (solo `self`; `wasm-unsafe-eval` para PDF.js), `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy`. Las respuestas de la API llevan `Cache-Control: no-store`. `/metrics`, `/health`, `/docs` y `/openapi.json` no se publican, y la documentación interactiva está desactivada.
- **Subidas:** Caddy admite hasta 320 MB y tiempos de 5 min; el límite efectivo es `MAX_UPLOAD_MB`.
- Un solo proceso `uvicorn` por contenedor (las métricas de proceso así lo suponen); escale con más contenedores detrás de Caddy si hace falta.

### Pruebas de rendimiento
Dos scripts en `backend/scripts/` (el segundo se ejecuta contra una API ya levantada):

- `bench_busqueda.py` crea una base **desechable** en el PostgreSQL indicado, la llena con vectores aleatorios de 1536 dimensiones y mide la consulta híbrida real. Comprueba que el fragmento buscado con su propio vector queda primero, que no se cuela ningún fragmento de otro tenant y el recall del índice HNSW.
- `carga_http.py` mide cuánto empeora una petición ligera mientras otros clientes inician sesión en masa.

**Búsqueda híbrida** (39 200 fragmentos, 21 tenants, PostgreSQL en Docker sobre un portátil con otras cargas):

| Escenario | p50 | p95 |
|---|---|---|
| Expediente normal (~700 fragmentos) | 62 ms | 66 ms |
| Tenant pequeño (200) entre los demás | 61 ms | 75 ms |
| Un único expediente de 15 400 fragmentos | 233 ms | 343 ms |
| 10 consultas simultáneas | 150 ms | 378 ms · 39 consultas/s |

Con filtros por tenant y expediente, PostgreSQL elige el índice `(tenant_id, expediente_id)` y ordena en exacto: el coste crece de forma lineal con el tamaño **del expediente**, no de la tabla. Un expediente típico (cientos o pocos miles de fragmentos) responde en 60–100 ms; el modelo generativo aporta 3–5 s más. El índice HNSW solo entraría en juego con expedientes muy grandes; si llegan a serlo, `RAG_HNSW_ITERATIVE` selecciona el modo de `hnsw.iterative_scan` (por defecto `strict_order`, que garantiza el orden exacto que necesita RRF).

**Inicio de sesión en masa** (30 logins simultáneos mientras se mide `GET /expedientes`):

| | Antes | Ahora |
|---|---|---|
| Petición ligera, **máximo** | 5–11 s (bucle de eventos congelado) | 0,5–0,8 s |
| Logins por segundo | 1,1–1,8 | 2,9–3,9 |
| Errores | 0 | 0 |

La mejora salió de un ejecutor de hilos acotado para bcrypt y de **liberar la conexión de base de datos antes de cada espera larga** (hash, Gemini, antivirus). Una primera versión con solo hilos provocó 15 errores 500 de 30: cada petición retenía su conexión mientras esperaba el hash y se agotaba el pool. `tests/test_conexiones.py` lo fija con un pool de **una sola conexión** (incluye una variante que reproduce el fallo para demostrar que la prueba lo detecta).

> Aviso al repetir `bench_busqueda.py`: la subconsulta que genera cada vector aleatorio debe depender de la fila. En una primera versión no lo hacía, PostgreSQL la evaluó una sola vez y **todos los fragmentos recibieron el mismo vector**, lo que invalidó esa primera ronda de mediciones. El script ya lo evita y deja el motivo documentado.

## Modelo de autorización
- Cada usuario pertenece a un tenant; todas las consultas filtran por `tenant_id`.
- `ADMIN_TENANT` administra usuarios, la política de borrado y todos los expedientes del tenant.
- Los demás roles acceden a un expediente solo con permiso explícito (`LECTOR` < `EDITOR` < `ADMIN`).
- Un expediente ajeno o sin permiso responde `404` (no revela que existe); un permiso insuficiente responde `403`.
