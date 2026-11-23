# Plan de desarrollo — MedTender RAG (Spring Boot + Python)

## Contexto
Plataforma multi-tenant para licitaciones médicas y auditoría en salud. El usuario conserva los PDF en su PC; el servidor guarda solo fragmentos, embeddings (pgvector) y metadatos. El PDF se elimina tras indexar (con verificación) y las consultas RAG funcionan con el PC apagado.

**Decisión de arquitectura.** El documento de requisitos asigna a **Spring Boot** la autenticación, la autorización, la recepción y la gestión de expedientes; el **agente de IA** vive en **Python**. Los Sprints 1–6 se construyeron enteramente en Python; los Sprints 7–10 incorporaron Java y dejaron cada lenguaje donde mejor encaja:

| Responsabilidad | Dónde | Tecnología |
|---|---|---|
| Identidad: login, JWT, usuarios, roles, tenants | **Java** (`api-java/`) | Spring Security + oauth2-resource-server, bcrypt |
| Expedientes y permisos LECTOR/EDITOR/ADMIN | **Java** | Spring Data JPA |
| Recepción de PDFs, firma, antivirus, SHA-256, estados, purga de rechazos | **Java** | Tika, PDFBox, cliente ClamAV INSTREAM |
| Límites de peticiones, auditoría de solo anexado, métricas | **Java** | Redis, Micrometer |
| Esquema de la base de datos | **Java** | Flyway (`V1…V8`), fuente única |
| Extracción, OCR, tablas, fragmentos, embeddings, purga tras indexar | **Python** (`agente/`, worker) | pypdfium2, pdfplumber, Tesseract, tiktoken, ARQ |
| Motor RAG: búsqueda híbrida RRF, citas verificables, abstención | **Python** | FastAPI, pgvector, Gemini |

## Arquitectura
```
React ──HTTPS──> Caddy ──> API Java (Spring Boot :8080)
                              │ JWT, tenants, permisos, expedientes, ingesta, límites, auditoría
                              │ HTTP interno + X-Internal-Token (tenant/usuario ya autorizados)
                              ▼
                        Agente FastAPI (:8000, red interna)      Worker ARQ (Python)
                          /internal/v1/documentos/{id}/procesar    extracción, OCR, fragmentos,
                          /internal/v1/consultas · /reindexaciones  embeddings, verificación, PURGA
                              └────── PostgreSQL 16 + pgvector · Redis · volumen efímero ──────┘
```
- **Java es la única puerta de entrada.** El agente no autentica usuarios: confía en el secreto compartido y acota siempre por el `tenant_id` que recibe.
- **El PDF cruza por un volumen efímero compartido:** Java lo escribe como `{id}.pdf`; el agente lo lee, verifica `COUNT(embedding) == total_chunks_esperados`, lo borra y deja el Acta de Purga. Java solo purga lo que él mismo rechaza.
- Los tokens JWT y los hashes bcrypt que emitió la primera versión (Python) siguen siendo válidos en Java.

## Decisiones técnicas
1. Python 3.12 con `uv`; Java 21 (compilado con el JDK 26 local) y Spring Boot 3.5.
2. `vector(1536)` fijo; `bge-m3` (1024) se rellena con ceros (la similitud coseno no cambia).
3. Un único enum de estados compartido entre BD, Java, Python y la UI.
4. Flyway es el dueño del esquema; las pruebas de Python aplican los mismos `.sql`.
5. File System Access API: solo Chrome/Edge sobre HTTPS/localhost.
6. Las citas se arman desde PostgreSQL: el LLM solo elige ids de fragmento; los extractos son literales verificados.
7. Se evitó PyMuPDF por su licencia AGPL (pypdfium2 + pdfplumber).

## Sprints

| Sprint | Contenido | Estado |
|---|---|---|
| 1 | Infraestructura, seguridad multi-tenant y expedientes (Python) | ✅ |
| 2 | Ingesta efímera: validación, SHA-256, estados, purga con Acta (Python) | ✅ |
| 3 | Extracción, OCR selectivo, tablas a Markdown y fragmentación | ✅ |
| 4 | Vectorización, EmbeddingRouter y re-vectorización sin PDF (Gemini) | ✅ |
| 5 | Motor RAG y frontend con visor local de PDF | ✅ |
| 6 | Endurecimiento: observabilidad, límites, auditoría, respaldos, HTTPS | ✅ |
| 7 | **Java:** esquema Flyway, JWT, usuarios, límites y auditoría | ✅ |
| 8 | **Java:** expedientes, permisos e ingesta (Tika, PDFBox, ClamAV) | ✅ |
| 9 | **Python como agente interno** + proxy de consultas y reindexación en Java | ✅ |
| 10 | Integración: compose dev/prod, imágenes, E2E, medición y documentación | ✅ |
| 11 | Rediseño del frontend: microscopio e histología, tema claro | ✅ |
| 12 | Rediseño del frontend: negatoscopio, tema oscuro | ✅ |
| 12b | Rediseño del frontend: paleta Geist/Inter y componentes redondeados | ✅ |
| 12c | Medicamentos de Colombia (datos abiertos de INVIMA, `V7`) | ✅ pendiente de integrar a `develop` |
| 13 | Orden del repositorio y documentación | ✅ |
| 14 | Aislamiento de tenants en la base (RLS, `V8`) | ✅ |
| 15 | Dimensión de vectores y verificación de modelos al arrancar | ✅ |
| 16 | Calidad de tablas, OCR y evidencia probatoria | ✅ |
| 17 | Endurecimiento de despliegue | ✅ |
| 18 | Frontend: identidad «Expediente / folio», dos temas, tokens semánticos y logotipo | ✅ |
| 19 | Frontend: espacio de trabajo del expediente | ✅ |
| 20 | Frontend: la cita como pieza central y visor acoplado | ✅ |
| 21 | Frontend: índice de expedientes y tablas de Medicamentos | ✅ |
| 22 | Frontend: portada e ingreso con el producto en acción | ✅ |
| 23 | Frontend: pulido (residuos, casos extremos, táctil) | ✅ |
| 24 | Salud: seguridad, consentimiento y cuentas personales (`V9`) | ✅ |
| 25 | Salud: anonimización antes de salir a la nube | ✅ |
| 26 | Salud: fotos y escaneos de documentos (JPG, PNG, HEIC) | ✅ |
| 27 | Salud: «Explícame este documento» | ✅ |
| 28 | Salud: medicamentos, efectos e interacciones con fuente (prospectos y fichas CIMA; cruce con documentos pendiente) | ✅ |
| 29 | Salud: evaluación de seguridad y cierre | ✅ |

Historias principales: aislamiento de tenants y permisos (1, 7, 8), PDF efímero con purga verificada (2, 8, 9), OCR y fragmentación 500–1000 tokens con 15 % de solape (3), embeddings por modelo del expediente (4), búsqueda híbrida RRF + citas con extractos literales + visor local con SHA-256 (5), observabilidad y auditoría (6, 7).

## Verificación
- **Java:** `mvn test` en `api-java/` con Postgres+pgvector y Redis reales (Testcontainers), clamd y agente simulados, HTTP real para el multipart.
- **Python:** `pytest` en `agente/` contra el esquema de Flyway.
- **Extremo a extremo:** stack Docker completo + Chrome (login → subir → pipeline → consulta con citas → visor local con SHA-256).
- Seguridad: ningún PDF queda en el volumen efímero tras indexar o rechazar; ninguna fila de otro tenant aparece en consultas.

## Desviaciones respecto a Requerimientos.md
El documento de requisitos original (`Requerimientos.md`, «Arquitectura RAG — Java, Spring Boot y pgvector») se cumple en su flujo de indexación y de consulta. Estas son las diferencias deliberadas:

| Requerimiento | Lo construido | Motivo |
|---|---|---|
| Todo en Java con Spring Boot | Java (identidad, expedientes, ingesta) + agente Python (OCR, embeddings, RAG) | Cada lenguaje donde mejor encaja; ver «Decisión de arquitectura» |
| OpenAI Embeddings en el MVP | Gemini (`gemini-embedding-001`); OpenAI y Ollama disponibles por configuración | Decisión del proyecto; el modelo se registra por expediente |
| `Pgvector.EntityFrameworkCore` | Spring Data JPA y SQL nativo con pgvector | Esa librería es de .NET y no aplica a Spring Boot |
| (no figura) | Módulo de medicamentos con datos abiertos de INVIMA | Alcance añadido; sin vectores, con citas a datos.gov.co |
| Tablas, firmas y sellos pueden exigir el original | Aviso por confianza de OCR; visor local con SHA-256 | Se profundiza en el sprint 16 |
