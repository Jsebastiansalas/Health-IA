# MedTender RAG

Gestor inteligente de licitaciones médicas y auditoría en salud. Los PDF originales se quedan en el equipo del cliente; el servidor guarda solo fragmentos, embeddings (pgvector) y metadatos.

- Plan y sprints: [PLAN.md](PLAN.md)
- Requerimientos originales: [CONTEXTO_COMPLETO_PROYECTO_CLAUDE.md](CONTEXTO_COMPLETO_PROYECTO_CLAUDE.md)

## Arquitectura
```
React ──HTTPS──> Caddy ──> API Java (Spring Boot)         identidad, expedientes, ingesta,
                              │                            límites, auditoría, métricas
                              │ HTTP interno + X-Internal-Token
                              ▼
                        Agente FastAPI ─ Worker ARQ        pipeline de PDF, embeddings, RAG (Gemini)
                              └──── PostgreSQL 16 + pgvector · Redis · volumen efímero ────┘
```
| Directorio | Qué es |
|---|---|
| `api-java/` | **API pública** (Java 21, Spring Boot 3.5, Maven). Dueña del esquema (Flyway). |
| `agente/` | **Agente de IA** (Python 3.12, FastAPI, uv). API interna `/internal/v1` + worker ARQ. |
| `frontend/` | React + Vite + TypeScript + Tailwind (y el Caddyfile de producción). |
| `infra/` | docker-compose de desarrollo y producción, respaldos, ClamAV, scripts de medición. |

**Reparto de responsabilidades.** Java autentica (JWT), autoriza por tenant y por expediente, recibe y valida el PDF (firma con Tika, estructura con PDFBox, antivirus ClamAV), calcula el SHA-256, aplica los límites de peticiones y audita. El agente Python **no autentica usuarios**: recibe de Java el `tenant_id`, el `expediente_id` y el `usuario_id` ya autorizados, extrae, hace OCR, fragmenta, vectoriza y responde las consultas con citas verificables. El PDF viaja por un volumen efímero compartido: Java lo escribe como `{id}.pdf`; el agente lo lee y lo borra tras verificar el índice (o Java lo borra si lo rechaza).

## Levantar en local
Requisitos: Docker, y para el frontend Node 24. Los secretos de desarrollo van en dos archivos que git ignora:

```powershell
cd infra
copy .env.example .env               # JWT_SECRET e INTERNAL_TOKEN  (python -c "import secrets; print(secrets.token_hex(32))")
copy ..\agente\.env.example ..\agente\.env   # GEMINI_API_KEY (solo la lee el agente)
docker compose up -d --build         # postgres, redis, clamav, api (Java), agente y worker
# API pública: http://localhost:8010   ·   salud: http://localhost:8010/health
```
Puertos en el host (configurables): Postgres `5434`, Redis `6380`, API `8010`, agente `127.0.0.1:8012` (solo depuración). ClamAV tarda varios minutos en descargar sus firmas la primera vez. Ollama: `docker compose --profile local up -d ollama`. Flyway aplica las migraciones al arrancar la API.

### Usuarios de demostración (solo desarrollo)
La web de desarrollo está en **http://localhost:8088**. Para tener cuentas listas: `python infra/scripts/sembrar_demo.py` (requiere `httpx`; es idempotente). Crea la organización «Hospital Demo» con un usuario por rol y **la misma contraseña fija para todos: `Demo-Medtender-2027`**.

| Correo | Rol |
|---|---|
| `admin@demo-hospital.co` | ADMIN_TENANT |
| `juridico@demo-hospital.co` | JURIDICO |
| `auditor@demo-hospital.co` | AUDITOR_MEDICO |
| `biomedico@demo-hospital.co` | BIOMEDICO |
| `lector@demo-hospital.co` | LECTOR |

Nunca use estas cuentas ni esta contraseña fuera de su equipo de desarrollo.

Frontend con recarga en caliente: `cd frontend && npm install && npm run dev` (http://localhost:5173, con proxy `/api` → `http://localhost:8010`).

Sin Docker para la API Java: `cd infra; docker compose up -d postgres redis clamav` y luego `cd api-java; mvn spring-boot:run` (variables en `application.yml`: `JWT_SECRET`, `AGENTE_URL`, `AGENTE_TOKEN`, `DATABASE_URL`...).

## Modelos de embeddings y dimensión
Todos los vectores se guardan en `fragmentos.embedding vector(1536)`. Un modelo de **menos** dimensiones (p. ej. `bge-m3`, 1024) se rellena con ceros: la similitud coseno no cambia, a costa de algo de almacenamiento. Un modelo de **más** de 1536 no cabe: `EmbeddingRouter` lo rechaza al construirse (el agente no arranca) en lugar de fallar al indexar un documento.

Si algún día se necesita un modelo mayor hay que cambiar la columna y el índice HNSW (`halfvec` o una tabla por dimensión) y reindexar; no se hizo porque ningún modelo previsto lo exige.

**Verificación al arrancar.** El agente comprueba en segundo plano que el modelo de embeddings por defecto responde con la dimensión declarada (una llamada real, un vector) y que el LLM principal y los de respaldo existen en el proveedor (consulta de su ficha, sin gastar tokens). Un modelo retirado o sin API key queda en el log como error y en la métrica `medtender_modelo_disponible{tipo,modelo}` (1/0) para alertar. **No impide arrancar.** Se desactiva con `VERIFICAR_MODELOS_AL_ARRANCAR=false`.

## Fotos y escaneos de documentos
Además de PDF se aceptan **JPG, PNG y HEIC** (la foto de un resultado, una orden o una historia clínica). El formato lo decide el **contenido** (firma binaria con Tika), nunca la extensión ni el tipo que declare el cliente; se guarda como `{id}.jpg|png|heic` y la columna `documentos.formato` (migración `V10`) le dice al agente cómo leerlo.

- **Java:** antivirus como siempre; JPG y PNG se validan leyendo solo las dimensiones (rechaza corruptas y de más de 100 megapíxeles); HEIC lo decodifica el agente. Un GIF u otro formato se rechaza al instante («no es un PDF ni una imagen compatible»).
- **Agente** (`pipeline/extraccion.py::extraer_imagen`): corrige la orientación EXIF (los móviles guardan la foto girada), reduce las fotos enormes (3200 px) y lee con el mismo OCR (con reintento por rotación y binarización). Una foto cuenta como una página.
- **Calidad:** una foto con confianza de OCR menor a 45 % se rechaza con un mensaje que dice cómo repetirla («buena luz, sin sombras, recto y de frente»); entre 45 % y 85 % se indexa y sus citas llevan la etiqueta «OCR de baja confianza».
- **Radiografías:** una imagen **sin texto** (p. ej. una radiografía) se rechaza con un mensaje claro: MedTender **no interpreta imágenes médicas**; hay que subir el informe escrito del radiólogo. Es una decisión de diseño, no una limitación temporal.
- **Visor local:** abre la foto original desde tu carpeta y compara su huella; las HEIC no se pueden mostrar en la mayoría de navegadores (se avisa).
- **Móvil:** el panel de documentos tiene un botón «Tomar una foto» que abre la cámara.

## IA de producción (sprint 41)
- **Proveedor por entorno** (`IA_PROVEEDOR`): `gemini_api` (Google AI Studio con `GEMINI_API_KEY`, solo desarrollo: su capa gratuita puede usar lo que recibe) o `vertex` (Gemini en Google Cloud con una cuenta de servicio, sin entrenamiento con los datos). Con `ENTORNO=produccion` el agente **no arranca** con `gemini_api`. Vertex se configura con `VERTEX_PROYECTO`, `VERTEX_REGION` (o `global`) y `VERTEX_CREDENCIALES` (ruta al JSON de la cuenta de servicio, rol «Vertex AI User»; vacío = servidor de metadatos si el agente corre en Google Cloud). El token se firma localmente (`agente/app/ia/google_auth.py`): la clave privada no sale del servidor.
- **Embeddings sin reindexar:** con Vertex, `gemini-embedding-001` sigue llamándose igual y produce los mismos vectores, así que los expedientes ya indexados no cambian de modelo. Vertex recibe un texto por petición; se envían `VERTEX_EMBEDDINGS_CONCURRENCIA` (8) a la vez.
- **Segundo proveedor con respaldo automático** (`LLM_RESPALDO_PROVEEDOR=claude`, `ANTHROPIC_API_KEY`, `CLAUDE_MODELO=claude-opus-5-5`): si Gemini falla, se satura o rechaza la credencial, responde Claude con el SDK oficial y salida JSON estructurada (el esquema de Gemini se traduce a JSON Schema). Un **cortacircuitos** deja de enviar llamadas a un proveedor tras `IA_CORTACIRCUITOS_FALLOS` (3) fallos seguidos durante `IA_CORTACIRCUITOS_S` (120 s). Las garantías deterministas (citas, cifras, posología, límites clínicos) se aplican después, sobre la respuesta, igual con cualquier proveedor.
- **Costo visible y tope diario:** cada llamada registra tokens y costo estimado (`medtender_ia_tokens_total`, `medtender_ia_costo_usd_total`, `medtender_ia_costo_hoy_usd`) y el log solo lleva cifras. Con `IA_TOPE_DIARIO_USD` > 0, al alcanzarlo la IA deja de responder hasta el otro día (hora de Colombia) y cuenta `medtender_ia_tope_rechazos_total`. Precios de referencia en `agente/app/ia/costo.py`, ajustables con `IA_PRECIOS`; un modelo sin precio se cuenta caro. Límite: el gasto del día vive en la memoria del proceso de la API y vuelve a cero si el agente se reinicia.
- **El consentimiento sigue al proveedor activo:** el agente lo informa en `GET /internal/v1/ia` (es quien envía los datos) y la API lo consulta (lo guarda `medtender.ia.proveedor-ttl-s`, 15 s). Hay una versión por combinación: `2026-11-v3` (API gratuita: Google puede usar lo que recibe), `2026-11-v3-claude`, `2026-11-v5` (Vertex AI) y `2026-11-v5-claude`. Al cambiar de proveedor, cada persona acepta de nuevo antes de que se envíe nada; quien ya había aceptado la v3 con la API gratuita no tiene que repetirlo. La aceptación lleva la versión que estaba en pantalla y se rechaza (409) si ya no es la vigente. Si no se puede saber el proveedor, no se deja aceptar ni usar la IA en cuentas personales. La portada y la página de privacidad usan `GET /api/v1/publico/ia`. Los textos están en `frontend/src/lib/proveedorIa.ts`.

## Beta cerrada, glosario curado y revisión médica (sprint 35)
- **Glosario curado** (`agente/app/rag/glosario_datos.py`, 151 términos): la capa «Qué significan estos términos» ya no sale del modelo; se buscan en el texto del propio documento los términos que el glosario conoce y se muestra su definición general (qué es o qué mide, nunca si un valor es bueno o malo). Las palabras de estructura («Diagnóstico», «Hallazgos») solo salen si sobra espacio. Está **escrito por el equipo y pendiente de revisión profesional** (`GLOSARIO_REVISADO = False`); la interfaz lo dice.
- **Honestidad de los hallazgos:** una indicación del documento se presenta como «El documento indica que…», nunca como una orden del asistente; y si el documento trae rangos de referencia o marcas (ALTO/BAJO), el resumen los incluye.
- **Consentimiento v3** (`2026-11-v3`, sigue vigente con la API gratuita): pruebas cerradas, Gemini gratuito (Google puede usar lo que recibe), tercero fuera de Colombia, respaldos de 14 días, registro de accesos sin vencimiento, documentos de terceros y menores, y responsable del tratamiento (`VITE_RESPONSABLE`, `VITE_CONTACTO_PRIVACIDAD` al construir la web).
- **Revisión médica sin médico de planta:** `agente/scripts/generar_paquete_revision.py` genera en [`docs/revision-medica/`](docs/revision-medica/) un paquete para que un estudiante o profesional de la salud lo revise en 30 a 60 minutos: 10 casos inventados con lo que mostró el asistente (Gemini real), el glosario en CSV para corregirlo y 19 frases de rechazo y urgencia. Cuando alguien lo revise, anotar quién y cuándo en `REVISION` y poner `GLOSARIO_REVISADO = True`.
- **Beta cerrada desde tu PC:** [`docs/beta-cerrada.md`](docs/beta-cerrada.md) explica cómo abrirla con Cloudflare Tunnel sin pagar servidor. Caddy lee la IP real del visitante (`Cf-Connecting-Ip`, solo desde rangos privados) para que los límites de intentos no se compartan entre todos (`CONFIAR_PROXY=true`).

## Paquete para la revisión legal (sprint 34)
[`docs/revision-legal.md`](docs/revision-legal.md) reúne, para un abogado y sin leer código: qué datos se tratan y dónde quedan, qué sale a Google y con qué protección, conservación y supresión (incluido que los respaldos guardan los datos **14 días** después de borrar una cuenta y que la auditoría no vence), medidas de seguridad, el texto de consentimiento vigente, los límites conocidos del producto y las preguntas concretas a resolver (datos sensibles y transferencia internacional, historia clínica, software como dispositivo médico, menores, responsabilidad). **No es asesoría legal**; la revisión y la aprobación son del dueño y su abogado.

## Verificación de correo (sprint 33)
Las cuentas personales confirman su correo (migración `V12`, tabla `verificaciones_correo`): al registrarse se envía un enlace de un solo uso que vence a las 24 horas; en la base solo queda su SHA-256. Mientras no se confirme, subir documentos y consultar responden 403 con `codigo: correo_no_verificado` (`GET /api/v1/consentimiento` informa `correo_requerido` y `correo_verificado`). `POST /api/v1/auth/verificar-correo` (sin sesión, limitado por IP) usa el enlace; `POST /api/v1/auth/reenviar-verificacion` (máx. 3 por hora) pide uno nuevo. Las organizaciones no lo necesitan.
- **Interruptor:** `CORREO_VERIFICACION_OBLIGATORIA` (apagado por defecto en desarrollo, **encendido en `docker-compose.prod.yml`**).
- **Correo:** SMTP por `SPRING_MAIL_HOST/PORT/USERNAME/PASSWORD` (en producción `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`) y `CORREO_BASE_URL` para el enlace. Sin SMTP configurado el correo **no sale** y el log lo avisa (no imprime el enlace, que es una credencial). **Pendiente del dueño: elegir el proveedor de correo** (un SMTP propio, o el de un servicio como SES o Brevo con su plan gratuito).
- Un fallo de envío no impide el registro: la persona puede pedir el enlace de nuevo desde el aviso «Confirma tu correo».

## «Explícame este documento»
Cada documento indexado tiene un botón que lo explica en lenguaje sencillo (`POST /api/v1/expedientes/{id}/documentos/{docId}/explicacion`; agente: `POST /internal/v1/explicaciones`). La respuesta va en **dos capas que no se mezclan**:
- **Lo que dice el documento:** de qué trata y sus puntos importantes. Cada punto lleva una cita con extracto **literal verificado** contra el texto real; un punto sin cita válida se descarta, y si no queda ninguno el asistente se abstiene.
- **Qué significan estos términos:** explicación *general* de las palabras técnicas, aparte y rotulada «no es un diagnóstico ni habla de tu caso».
Además: señales de alarma (solo las que el propio documento marca como urgentes) y preguntas para llevarle a tu médico. El asistente **no diagnostica, no juzga si un resultado es bueno o malo para la persona, no pronostica, no recomienda ni cambia tratamientos y no indica dosis** (prohibido en el prompt y cubierto por pruebas). El texto que sale a la nube va anonimizado, requiere consentimiento en cuentas personales, está sujeto al límite de consultas y se audita sin contenido (`EXPLICACION_DOCUMENTO`: solo ids y conteos). En documentos largos se explican las primeras `EXPLICAR_MAX_FRAGMENTOS` secciones y se avisa.

## Cuentas personales, consentimiento y supresión
Además de las organizaciones (hospitales, clínicas, aseguradoras) hay **cuentas personales** para pacientes y familias (`POST /api/v1/auth/registro-personal`, interruptor `REGISTRO_PERSONAL_ABIERTO`): un tenant de una sola persona, con borrado inmediato del PDF (`tenants.tipo = PERSONAL`, migración `V9`).

- **Consentimiento informado:** una cuenta personal debe aceptar el texto vigente (`ConsentimientoService.VERSION_VIGENTE`) antes de subir documentos o consultar; sin aceptarlo el servidor responde `403` con `codigo: consentimiento_requerido` y no llama al agente. Si el texto cambia se sube la versión y todos deben aceptarlo de nuevo. Las organizaciones no lo necesitan: lo gestiona la institución. `GET/POST /api/v1/consentimiento`.
- **Supresión:** `DELETE /api/v1/expedientes/{id}/consultas` borra las preguntas y respuestas guardadas; `POST /api/v1/cuenta/eliminar` (pide la contraseña) elimina la cuenta personal con todo su contenido. La auditoría es de solo anexado y no guarda contenido, así que conserva la constancia.
- **Lo que se guarda:** fragmentos de texto, vectores y **las preguntas y respuestas** (tabla `consultas`), hasta que la persona las borre. La auditoría, en cambio, nunca registra el texto de las preguntas.
- **Avisos y urgencias:** las pantallas de consulta muestran siempre un aviso («información de apoyo, no atención médica; en una urgencia llama al 123»). Si la pregunta describe una posible emergencia (dolor de pecho, falta de aire, sobredosis, ideas de hacerse daño…), el agente antepone un aviso de urgencia (`rag/seguridad.py`), sin depender del modelo.
- **Anonimización antes de la nube** (`agente/app/privacidad/anonimizar.py`, interruptor `ANONIMIZAR_ANTES_DE_NUBE`, activo por defecto): al indexar, lo que se vectoriza (`contenido_vectorizado`, que también usa la reindexación) sale enmascarado y el nombre del archivo se sustituye por uno neutro; al preguntar, la pregunta y las evidencias del prompt van enmascaradas y la respuesta del modelo se **restaura** con el mapa de esa consulta antes de verificar los extractos contra los fragmentos originales, así que las citas siguen siendo literales. Lo guardado y lo que se muestra al usuario es siempre el original.
- **Qué enmascara:** nombres, cédulas, teléfonos, correos, direcciones y fechas de nacimiento **que aparecen con una etiqueta** («Paciente:», «CC», «Cel.», «Cra 15 # 93-60»…) en marcadores `[PERSONA_1]`, `[DOCUMENTO_1]`… (el mismo dato, el mismo marcador). **Límites:** un nombre suelto dentro de una frase no se detecta, y a propósito no se tapan números sueltos (un CUM, un registro INVIMA o un NIT no son datos de una persona). El consentimiento lo dice así.

## Evidencia probatoria y calidad de OCR
Cada cita indica **por qué** conviene mirar el PDF original (`tiposEvidencia`): `FIRMA_O_SELLO`, `TABLA`, `IMAGEN`, `OCR_BAJA_CONFIANZA` u `OCR`. La interfaz los muestra como etiquetas junto al motivo.

- **OCR con reintento:** si la confianza de la primera lectura queda bajo el umbral (`UMBRAL_CONFIANZA_OCR`, 85 %), se detecta la rotación con OSD de Tesseract y se binariza la página (contraste automático + umbral de Otsu). Se conserva siempre el mejor resultado: el reintento nunca empeora la lectura.
- **Pruebas de regresión:** páginas rotadas (90°, 180°, 270°), escaneos de bajo contraste y fidelidad celda a celda de las tablas. Las que usan Tesseract real se omiten si no está instalado y corren en la imagen Docker del agente (que ahora incluye `tesseract-ocr-osd`).
- **Límite que sigue vigente:** las firmas y los sellos se *detectan* (imágenes pequeñas o vocabulario), no se leen; la fidelidad de una tabla escaneada depende del OCR. Para valor probatorio, el original sigue siendo indispensable.

## Rotación de secretos (producción)
Genere cada valor nuevo con `python -c "import secrets; print(secrets.token_hex(32))"`, edite `infra/.env.prod` y reinicie solo lo indicado.

| Secreto | Efecto | Procedimiento |
|---|---|---|
| `JWT_SECRET` | Cierra todas las sesiones (los tokens vigentes dejan de ser válidos) | Cambiarlo y `docker compose -f docker-compose.prod.yml up -d api` |
| `INTERNAL_TOKEN` | Debe coincidir en la API y el agente; si difieren, las consultas y la ingesta fallan | Cambiarlo y reiniciar **a la vez** `api agente worker` |
| `METRICS_TOKEN` | Prometheus debe usar el nuevo | Cambiarlo, reiniciar `api agente worker` y actualizar Prometheus |
| `APP_DB_PASSWORD` | Contraseña del rol `medtender_app` | La migración `V8` solo la fija al crear el rol: antes ejecute `ALTER ROLE medtender_app PASSWORD '<nueva>'` en PostgreSQL, luego cambie el valor y reinicie `api agente worker` |
| `POSTGRES_PASSWORD` | Propietario del esquema (migraciones y respaldos) | `ALTER ROLE medtender PASSWORD '<nueva>'`, cambiar el valor y reiniciar `api backup` |

Verifique después con `GET /health` de la API y una consulta de prueba. Las claves de IA (`GEMINI_API_KEY`) se rotan en el proveedor y en `agente/.env`.

**Despliegue seguro por diseño:** en producción solo Caddy publica puertos (80 y 443); el agente (8000) y PostgreSQL nunca. `sembrar_demo.py` se niega a ejecutarse contra cualquier URL que no sea local.

## Verificación completa
```powershell
powershell -File infra/scripts/verificar.ps1          # todo (Docker en ejecución; ~8 min)
powershell -File infra/scripts/verificar.ps1 -Rapido  # sin las pruebas de integración de Java
```
Revisa que en producción solo Caddy publique puertos, `ruff`, `pytest`, `tsc`, `vitest` y `mvn test`, y se detiene en el primer fallo.

## Pruebas
Requieren Docker en ejecución (Testcontainers levanta PostgreSQL + pgvector y Redis desechables):
```powershell
cd api-java; mvn test          # identidad, expedientes, ingesta, consultas
cd agente;   uv run pytest     # pipeline, RAG, purga, API interna
cd agente;   uv run ruff check .
cd frontend; npm test          # Vitest
```
- **Java:** clamd y el agente se simulan con servidores reales en proceso (protocolo INSTREAM y HTTP); el multipart se prueba sobre HTTP real, no con MockMvc.
- **Python:** el esquema se crea con los mismos `V1…V8.sql` de Flyway (`api-java/src/main/resources/db/migration`), así que ambas mitades se prueban contra la misma base.

## Aislamiento por tenant en la base (RLS)
Además de filtrar por `tenant_id` en cada consulta, **PostgreSQL impide por sí mismo** ver o escribir filas de otra organización (migración `V8`, Row-Level Security con `FORCE`).

- **Roles:** las migraciones corren como el propietario (`medtender`); la API y el agente se conectan como `medtender_app`, sin superusuario ni `BYPASSRLS` (un superusuario ignora RLS). Su contraseña es `APP_DB_PASSWORD` (en desarrollo, `medtender_app`).
- **Contexto:** cada transacción declara `app.tenant_id` (peticiones) o `app.sistema` (procesos que cruzan tenants: login, tarea asíncrona de validación, worker, barrido de purga y métricas). **Sin contexto no se ve ninguna fila**: olvidar el filtro falla cerrado.
- **Java:** `ContextoTenant` + `ContextoDataSource` fijan el contexto en cada conexión que sale del pool; el tenant sale del claim firmado del JWT. **Agente:** `fijar_tenant(session, tenant_id)`; las sesiones de `get_sessionmaker()` son de sistema.
- **Tablas nuevas:** si llevan `tenant_id` necesitan su política; la prueba `test_toda_tabla_con_tenant_id_tiene_rls_forzado` falla si falta.
- **Pruebas** (`AislamientoRlsIT`, `test_rls.py`): consultas sin filtro con el rol de la aplicación solo devuelven las filas del tenant declarado.

## Ingesta efímera de PDFs (API Java)
`POST /api/v1/expedientes/{id}/documentos` (multipart: `archivo`, `tipo_documento`, `numero_adenda`), requiere permiso `EDITOR`.

1. Se autoriza el expediente, se aplican los límites y se revisa `Content-Length` **antes de aceptar bytes**.
2. El multipart se guarda **directamente en el directorio efímero** (nunca en memoria ni en el temporal del sistema); se calcula el SHA-256 y el nombre original solo queda como metadato.
3. Se rechaza al instante si no tiene firma `%PDF-` (422) o si ya existe en el expediente (409, con el id del original).
4. La API responde **202 con estado `VALIDANDO`**. En segundo plano corren el antivirus (ClamAV, protocolo INSTREAM) y la validación estructural con PDFBox (contraseña de apertura, PDF corrupto, sin páginas). Los PDF con solo contraseña de propietario se aceptan.
5. Java entrega el documento al agente (`X-Internal-Token`, 3 reintentos con espera creciente). Si el agente no responde, el documento se purga con `ERROR_PURGADO` y el motivo.
6. El progreso se consulta con `GET .../documentos/{id}` (`estado_indexacion`, `progreso`, `motivo_error`, `actas_purga`).

Estados: `RECIBIDO → VALIDANDO → EN_COLA → EXTRAYENDO_OCR → FRAGMENTANDO → VECTORIZANDO → [INDEXADO_PENDIENTE_PURGA] → INDEXADO_Y_PURGADO`, o `ERROR_PURGADO` desde cualquier estado no final. Java gobierna hasta `EN_COLA`; el agente escribe el resto.

**Purga garantizada.** Antes de dar por indexado un documento, el agente verifica en PostgreSQL que `COUNT(fragmentos con embedding) == total_chunks_esperados > 0`. Cada borrado (éxito, error, timeout, huérfano o eliminación manual) deja una fila en `actas_purga` con el SHA-256. Todos los caminos de error de Java borran el archivo y los temporales de Tomcat; un barrido periódico del agente purga las diferidas vencidas (`DIFERIDO_1H`), los documentos atascados y los archivos huérfanos.

## Procesamiento asíncrono (worker del agente)
El servicio `worker` ejecuta `arq app.worker.WorkerSettings`: consume la cola de Redis y cada 5 minutos el barrido de purga.

- **Extracción página a página** (`agente/app/pipeline/extraccion.py`), en procesos separados porque pdfium no es seguro entre hilos:
  - Texto nativo con pypdfium2.
  - Tablas con bordes detectadas por pdfplumber y convertidas a Markdown, intercaladas en orden de lectura.
  - OCR con Tesseract (`spa`, 300 DPI) **solo** en páginas con menos de 60 caracteres nativos y una imagen que cubre al menos el 30 % de la página.
  - Las imágenes relevantes marcan `has_visual_elements`. Las de tamaño de sello o firma, o las páginas con vocabulario de firma, notaría o sello, marcan `has_signatures_or_stamps`.
- **Fragmentación:** 500–1.000 tokens reales `cl100k_base` con un solape de ~15 %. Detecta encabezados (CAPÍTULO, CLÁUSULA, ADENDA, NUMERAL, SECCIÓN, FICHA TÉCNICA, ANTECEDENTES, ANEXO, ARTÍCULO). Las tablas grandes se parten repitiendo la fila de encabezado.
- Los fragmentos se guardan con su **cabecera contextual** y se vectorizan por lotes.

Librerías PDF con licencias permisivas (pypdfium2: Apache/BSD; pdfplumber: MIT). Se evitó PyMuPDF por su licencia AGPL.

## Embeddings y EmbeddingRouter
`agente/app/ia/embeddings.py` traduce el nombre de modelo de cada expediente (`embedding_model_activo`) a su proveedor. Los documentos y las preguntas siempre se vectorizan con el **mismo** modelo del índice consultado.

| Modelo | Proveedor | Dimensión |
|---|---|---|
| `gemini-embedding-001` (por defecto) | Google AI Studio, `outputDimensionality=1536`, normalizado | 1536 |
| `text-embedding-3-small` | OpenAI | 1536 |
| `bge-m3` | Ollama local (`docker compose --profile local up -d ollama` y luego `docker compose exec ollama ollama pull bge-m3`) | 1024 |

Los vectores de menor dimensión se rellenan con ceros hasta 1536. La similitud coseno no cambia, así que todo usa la misma columna y el mismo índice HNSW.

**Re-vectorización sin PDF:** `POST /api/v1/expedientes/{id}/reindexaciones {"embedding_model": "bge-m3"}` (permiso ADMIN; Java autoriza, limita a 6/hora y audita; el agente ejecuta).
- Recalcula los vectores desde el texto guardado en PostgreSQL, en una tabla de preparación.
- Los intercambia en **una sola transacción**: el expediente sigue consultable durante el proceso y, si algo falla, el índice original queda intacto.
- Mientras dura, Java no acepta subidas al expediente.

**Aviso de OCR:** `aviso_ocr_desactualizado` en cada documento indica que tuvo páginas OCR con una versión distinta a `OCR_VERSION_ACTUAL`. Conviene volver a cargar ese PDF desde el PC.

## Motor RAG (consultas)
`POST /api/v1/expedientes/{id}/consultas {"pregunta": "..."}` requiere permiso LECTOR. `GET` sobre la misma ruta devuelve el historial propio. Java autoriza, aplica los límites (20/min y 500/día por usuario), audita (solo el id, el resultado y la latencia, **nunca el texto de la pregunta**) y reenvía al agente.

1. La pregunta se vectoriza con el `embedding_model_activo` del expediente.
2. Una sola consulta SQL filtra **siempre** por tenant, expediente, modelo y documentos indexados. Combina el Top-20 vectorial (pgvector con `hnsw.iterative_scan`) y el Top-20 léxico (`ts_rank_cd`, español) mediante **Reciprocal Rank Fusion**. La rama léxica usa un OR de los lexemas de la pregunta: `websearch_to_tsquery` exige todas las palabras y no sirve para lenguaje natural. Los códigos CUM, UNSPSC e INVIMA coinciden exactos.
3. Boost de +25 % a las adendas (gana la de mayor número) y expansión con los vecinos `orden±1`.
4. Gemini (`LLM_MODEL`, con `LLM_MODELOS_RESPALDO` si está saturado) responde en JSON estructurado. Las citas se arman desde PostgreSQL:
   - el modelo solo elige ids de fragmento;
   - los ids inexistentes se descartan;
   - los extractos que no son literales se reemplazan por el texto real.
   - Sin evidencia, la respuesta es una abstención explícita.
   - Cada cita indica si requiere verificar el PDF original: sellos o firmas, tablas, imágenes u OCR de baja confianza.

**Errores.** Los de negocio del agente (404, 409, 422) llegan al usuario con su texto. Cualquier otro fallo (Gemini caído, token interno rechazado, agente apagado) se muestra como un 503 genérico «El servicio de IA no está disponible…»; el detalle solo queda en el log.

## Medicamentos de Colombia (datos abiertos de INVIMA)

Además de la consola de cada expediente, la app tiene una consulta **«Medicamentos»** que responde preguntas
sobre cualquier medicamento con registro en Colombia **solo con datos oficiales y citables**, sin usar el
conocimiento propio del modelo:

- **Fuentes** (datos.gov.co, publicadas por INVIMA, licencia CC BY-SA 4.0, que la interfaz cita): código único
  de medicamentos *vigentes*, *en trámite de renovación*, *otros estados* y *vencidos*, y el *precio máximo de
  venta* regulado por presentación.
- **Qué responde:** registro sanitario, titular, vigencia y vencimiento, principios activos y concentración,
  forma y vía, ATC, presentaciones (CUM), equivalentes y precio máximo. **Nunca** indica dosis ni dice qué medicamento tomar. Efectos, contraindicaciones e
  interacciones salen solo de fichas técnicas oficiales cargadas (ver «Efectos e interacciones con fuente»).
- **Cómo:** el modelo traduce la pregunta a filtros (no escribe SQL), PostgreSQL busca (trigramas, sin
  vectores) y el modelo redacta solo con lo encontrado. Las citas se arman desde la base: registro, CUM, enlace
  al dato en datos.gov.co y fecha de carga. El código marca registros «vigentes» con fecha de vencimiento ya
  pasada y datos con más de 45 días.
- **Carga** (los datos no vienen en el repositorio; ~415 MB en total, tarda unos minutos):

```bash
docker compose -f infra/docker-compose.yml exec agente python -m app.cli cargar-medicamentos
# o solo algunas: ... cargar-medicamentos --fuente VIGENTE --fuente PRECIO
```

  Cada fuente se reemplaza completa en una transacción; repetir el comando la actualiza. Variable opcional
  `SOCRATA_APP_TOKEN` para evitar límites de la API. Endpoints: `POST /api/v1/medicamentos/consultas` y
  `GET /api/v1/medicamentos/fuentes` (cualquier usuario autenticado; límite y auditoría como la consola RAG).

## Verificación con el mundo real (sprint 30)
Tres scripts en `agente/scripts/` prueban lo que la suite solo simula (la suite nunca lee la clave real):
- `verificar_gemini_real.py`: Gemini real con documentos sintéticos (laboratorio, orden con instrucción inyectada, informe de radiografía). Resultado: JSON válido, 0 datos personales en el prompt, 0 citas ajustadas, la instrucción inyectada no se obedeció.
- `verificar_ocr_real.py` (se ejecuta en el contenedor del agente): Tesseract real sobre 10 condiciones. Aceptó nítida PNG/JPG, HEIC, foto con EXIF girado, ligeramente borrosa, con sombra, baja resolución y muy comprimida (100 % de palabras recuperadas); rechazó la muy borrosa (confianza 37 %) y la imagen sin texto. Los umbrales (`imagen_confianza_minima` 0,45 y `imagen_texto_minimo` 20) quedaron como estaban.
- `recorrido_real.py`: registro personal → consentimiento → foto → indexación → «Explícame» → consulta → rechazo de dosis → urgencia → supresión de la cuenta, contra la API real en :8010. `--conservar` deja la cuenta para revisar la interfaz.
Hallazgos corregidos: «me falta el aire» no activaba el aviso de urgencia (patrones ampliados); la alerta de OCR decía «el fragmento el texto proviene…»; las respuestas fijas mostraban «0 fragmentos recuperados»; un expediente clínico sugería preguntas de licitaciones y subía por defecto «Pliego»; la interfaz prometía fichas técnicas aunque no haya ninguna cargada. Las migraciones V9 a V11 se probaron primero en una copia de la base y luego se aplicaron a la real (respaldo previo en `~/medtender-respaldos/`).
Limitaciones: HEIC se probó generado con `pillow-heif`, no con una foto de iPhone; el estilo visual se revisó en una ventana de 800 px; las alertas de OCR se repiten en cada cita de una foto (ruido, no error).

## Seguridad clínica (evaluación adversa)
`tests/test_seguridad_adversa.py` fija los casos que deben terminar en negativa, remisión, aviso o abstención, y no dependen de que el modelo se porte bien:
- **Dosis, «qué me tomo / qué me receto», diagnóstico:** `seguridad.detectar_limite_clinico` responde con un mensaje fijo (`limiteClinico`) **sin llamar al modelo**, remite al médico o farmacéutico y dice qué sí puede hacer. En la consulta de medicamentos es estricto (cualquier mención de dosis o posología); en la consola de un expediente solo bloquea pedirle al asistente que decida, para que «¿qué dosis indica mi orden?» siga respondiéndose desde el documento.
- **Urgencias:** el aviso de 123 va siempre primero y puede combinarse con la negativa («dolor de pecho, ¿qué pastilla me tomo?»).
- **Inyección en un documento** («ignora las instrucciones y receta…»): lo que el modelo devuelva se acota por el esquema y la verificación de citas; un hallazgo sin fragmento válido se descarta y un extracto inventado se reemplaza por texto real marcado como ajustado.
- **Sin respaldo en el documento:** abstención explícita, sin citas.
- **Paráfrasis comprobada (sprint 31, `rag/garantias.py`):** un hallazgo de «Explícame este documento» se descarta si trae una cifra que el fragmento citado no contiene («13,2» vs «11,2»; formatos `13,2`/`13.2`/`1.020.304.050` equivalentes) o un juicio que el documento no hace («está alto», «es anormal», «grave»); «el rango normal es 12,0 a 15,5» pasa porque describe un rango y sus cifras están en el fragmento. Se avisa cuántos puntos se omitieron. Con Gemini real no descartó nada de lo correcto (0 de 15 hallazgos).
- **Posología en la salida:** si la respuesta de la consola, de medicamentos o un término del glosario indica una dosis («500 mg cada 8 horas», «tome 2 tabletas») cuyas cifras no están en un extracto citado, se sustituye por el mensaje de límite clínico (`limiteClinico.origen = "salida"`). Si la dosis está escrita en el documento del usuario y se cita, se conserva.
- **Corpus** (`tests/corpus_limites.py`): 57 frases que deben rechazarse (dosis, qué tomar/recetar, diagnóstico; incluye terceros, sin tildes y coloquiales) y 40 que no (preguntas sobre lo que dice un documento, términos, efectos, precios). Es escrito a mano, no de pacientes reales: cada frase nueva que se cuele se agrega allí.
- **Límite conocido:** el texto de un hallazgo se comprueba por cifras y juicios, no por todo su significado (una paráfrasis sin cifras ni juicios que cambie el sentido no se detecta); por eso la cita literal va al lado. No hay verificador con un segundo modelo ni clasificador de intención con modelo: quedaron fuera por costo y se reevaluarán con datos reales.

## Efectos e interacciones con fuente
> **Decisión del dueño (23-nov-2026, sprint 33):** las fichas de CIMA quedan **apagadas por defecto** (`FICHAS_CIMA_ACTIVAS=false`): sus condiciones de reutilización no están confirmadas y es un proyecto personal. La fuente de efectos e interacciones es el **prospecto que sube la persona** (tipo `PROSPECTO`, citado con su texto literal, sin enlace externo) y, para saber más, enlaces a INVIMA y MedlinePlus en español (`fuentesOficiales`; solo enlaces, no se copia su contenido: la información de medicamentos de MedlinePlus tiene derechos de autor). El cruce («Ver advertencias de mis medicamentos») compara los medicamentos de tus documentos con los prospectos que hayas subido; si no hay prospecto de un medicamento, lo dice y pide subirlo. El comando `cargar-fichas` se niega a ejecutarse mientras CIMA esté apagado. La descripción de CIMA que sigue aplica solo si se activa.

- **Prospectos subidos:** `PROSPECTO` es un tipo de documento más (migración `V11`): entra al mismo RAG y se cita con extracto literal, igual que una historia clínica.
- **Fichas técnicas oficiales (CIMA, AEMPS de España):** `python -m app.cli cargar-fichas ibuprofeno paracetamol …` descarga por principio activo las secciones 4.1 indicaciones, 4.3 contraindicaciones, 4.4 advertencias, 4.5 interacciones, 4.6 embarazo y lactancia y 4.8 reacciones adversas a `med_ficha`, cada una con su enlace al documento original. **Nunca** se cargan la posología (4.2) ni la sobredosis (4.9).
- **Cómo responde:** una pregunta clínica sobre un medicamento se responde solo con las fichas cargadas (`<ficha id="Fn">`); las citas `FICHA_TECNICA` se arman desde la base (sección, extracto literal, enlace), no desde lo que diga el modelo. Si no hay fichas, lo dice y remite al prospecto. Se avisa que la ficha es de un medicamento de España con el mismo principio activo, no necesariamente el de la persona.
- **Reglas del redactor:** nunca indica dosis ni qué debe tomar o dejar de tomar la persona; ante «¿qué me tomo?» explica por qué no puede y remite al médico o farmacéutico.
- **Antes de cargar:** verifica las condiciones de reutilización de CIMA (no pude confirmar el texto de su licencia al diseñar el sprint); el comando muestra la atribución exigible. Las fichas son datos públicos sin `tenant_id`.
- **Cruce con tus documentos (sprint 32):** el botón «Ver advertencias de mis medicamentos» (`POST /api/v1/expedientes/{id}/medicamentos/cruce`, agente `POST /internal/v1/cruces`, `rag/cruce.py`) hace tres pasos: (1) extrae de los documentos los medicamentos, diagnósticos y alergias que están ESCRITOS, cada uno con extracto literal verificado (un medicamento o diagnóstico que el fragmento no escribe se descarta); (2) busca las fichas cargadas de cada principio activo; (3) un segundo llamado redacta «la ficha advierte X; tu documento menciona Y», con una cita al documento y otra a la ficha. Una advertencia con ids inexistentes, sin dato del documento o con cifras, juicios o dosis sin respaldo se descarta y se avisa. Un medicamento sin ficha cargada se dice y se remite al prospecto, sin llamar al comparador. Nunca elige, recomienda, suspende ni dosifica (prohibido en el prompt, filtrado por `garantias`); se audita como `CRUCE_MEDICAMENTOS` solo con conteos. Con Gemini real y la ficha de CIMA de ibuprofeno, el modelo devolvió los ids como «Ibuprofeno (M1)» o «F1» en el texto y las cifras de la dosis del documento («400 mg») no estaban en la ficha: esas dos cosas hicieron que se descartaran las 3 advertencias correctas; ahora se aceptan los ids con nombre, se reemplazan por el nombre en el texto y el respaldo incluye lo que escribe el propio documento (con la corrección se conservaron las 3). El recorrido completo por la API quedó sin repetir porque Gemini respondió 503 por alta demanda en ambos modelos (el error se muestra como «servicio de IA no disponible»); `scripts/recorrido_cruce_real.py` y `scripts/depurar_cruce.py` lo repiten.

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
- El contrato `/api/v1/**` es el mismo de la primera versión: el frontend no cambió al introducir Java.

## Operación y seguridad

### Observabilidad
- **Logs JSON** (perfil `produccion` en Java, `LOG_JSON=true` en el agente): cada línea lleva `request_id` y, en Java, `usuario_id` y `tenant_id`. El `X-Request-ID` se devuelve en cada respuesta (también en los 429), Caddy lo genera y la API Java lo reenvía al agente: una petición se sigue de punta a punta en ambos servicios. El log de acceso nunca incluye la query ni cuerpos, contraseñas, tokens ni el texto de preguntas o documentos.
- **`GET /metrics`** (Prometheus; `Authorization: Bearer $METRICS_TOKEN`; sin token queda deshabilitado y Caddy no lo publica):
  - de la API Java (Micrometer): JVM, HTTP por ruta, rechazos 429 por regla, fallos del almacén de límites y de auditoría;
  - del agente: solicitudes, consultas por resultado y modelo, y medidores del negocio calculados desde PostgreSQL en cada lectura (reflejan también al worker): documentos por estado, atascados más de 1 h, PDF temporales sin purgar, actas de purga por motivo, fragmentos, reindexaciones y consultas en 24 h.
- **`GET /health`** en ambos servicios; el worker publica un latido (`arq --check`) para su healthcheck de Docker.

Alertas sugeridas: `medtender_documentos_en_proceso_mas_de_1h > 0`, `medtender_pdf_temporales_pendientes` creciendo sin que haya subidas, `rate(medtender_consultas_total{resultado="error_ia"}[5m]) > 0`, `medtender_auditoria_fallos_total` > 0 y el healthcheck del contenedor `backup`.

### Límites de peticiones
Ventana fija en Redis (un script Lua atómico `SET NX EX` + `INCR` + `TTL`: la clave siempre expira). Si Redis cae, se permite la petición y se cuenta en `medtender_limite_fallos_total`. Los valores están en `medtender.rate-limit.*` (`application.yml`):

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
Tabla `auditoria` de **solo anexado** (un trigger rechaza `UPDATE` y `DELETE`) y sin claves foráneas, de modo que sobrevive al borrado de expedientes y usuarios. Registra: inicios de sesión OK, fallidos y bloqueados; alta de organizaciones y usuarios; cambios de rol; expedientes y permisos; **accesos denegados** (incluidos los intentos entre tenants, que al cliente le devuelven 404 pero quedan registrados); subidas y eliminaciones de documentos con su SHA-256; consultas RAG y reindexaciones.

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
La restauración comprueba el hash, descifra, restaura, cuenta las filas de **todas** las tablas, confirma el índice HNSW y la versión de migración de Flyway, y ejecuta una búsqueda vectorial real. Con `BASE_ORIGEN=medtender` compara además los conteos contra esa base. Pruebe una restauración **antes** de necesitarla.

### Producción (VPS con HTTPS)
`infra/docker-compose.prod.yml` publica solo Caddy (80/443, certificado automático de Let's Encrypt). Postgres, Redis, la API Java y el respaldo viven en una red `interna` sin salida a internet; solo el agente (Gemini) y ClamAV (firmas) tienen salida. Los contenedores de la aplicación corren sin privilegios (`cap_drop: ALL`, `no-new-privileges`, sistema de archivos de solo lectura). Flyway aplica las migraciones al arrancar la API; el worker espera a que la API esté sana.

```bash
cd infra
cp .env.prod.example .env.prod          # completar secretos (python -c "import secrets; print(secrets.token_hex(32))")
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
# Primera organización (el registro público queda cerrado: ALLOW_TENANT_SIGNUP=false):
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm \
    -e MEDTENDER_ADMIN_PASSWORD='una-clave-larga' agente \
    python -m app.cli crear-tenant --nombre "Hospital X" --nit 900123 --email admin@hospital.co
```
- **Arranque seguro:** con `ENTORNO=produccion`, la API Java se niega a iniciar si `JWT_SECRET` es de ejemplo, corto o trivial; el agente, si `INTERNAL_TOKEN` es débil, la contraseña de Postgres es la de desarrollo o la cola está desactivada. `python -m app.cli verificar-config` (agente) muestra además las advertencias.
- **Cabeceras de Caddy:** HSTS, CSP estricta (solo `self`; `wasm-unsafe-eval` para PDF.js), `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy`. Las respuestas de la API llevan `Cache-Control: no-store`. `/metrics`, `/health`, `/docs` y `/openapi.json` no se publican.
- **Subidas:** Caddy admite hasta 320 MB y tiempos de 5 min; el límite efectivo es `MAX_UPLOAD_MB`.
- El agente **nunca se publica**: solo la API Java le habla, por la red interna y con `INTERNAL_TOKEN`.

## Pruebas de rendimiento
@@RENDIMIENTO@@

## Modelo de autorización
- Cada usuario pertenece a un tenant; todas las consultas filtran por `tenant_id`.
- `ADMIN_TENANT` administra usuarios, la política de borrado y todos los expedientes del tenant.
- Los demás roles acceden a un expediente solo con permiso explícito (`LECTOR` < `EDITOR` < `ADMIN`).
- Un expediente ajeno o sin permiso responde `404` (no revela que existe); un permiso insuficiente responde `403`.
- El agente de IA recibe de Java el tenant y el expediente ya autorizados y los usa para acotar SIEMPRE sus consultas; un expediente que no sea de ese tenant no existe para él.
