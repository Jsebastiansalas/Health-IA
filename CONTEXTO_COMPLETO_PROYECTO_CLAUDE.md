# Contexto Maestro del Proyecto para Claude (System & Architecture Context)

> **Instrucciones para Claude:**  
> Este documento contiene **todo el contexto funcional, arquitectónico, técnico y de reglas de negocio** del proyecto que vamos a desarrollar. Léelo íntegramente y úsalo como tu fuente de verdad absoluta. Cada línea de código, esquema SQL, endpoint y pantalla que construyas debe respetar estrictamente los requerimientos y flujos descritos aquí.

---

## 1. Documento Base de Requerimientos Originales (Innegociables)

El proyecto nace del siguiente documento oficial de arquitectura que debe cumplirse al **100%**:

### Objetivo
Permitir que cada cliente conserve los PDF originales en su computador mientras consulta y analiza su contenido desde cualquier lugar. En el VPS se almacenan fragmentos de texto, embeddings y metadatos; **no se necesita que el computador esté encendido para consultar el texto ya indexado**.

### Componentes Requeridos
* **Cliente web:** Carga temporal de PDF por HTTPS.
* **Spring Boot:** Autenticación, autorización, recepción y gestión de expedientes.
* **Procesador asíncrono en Servidor:** Extracción de texto, OCR cuando sea necesario, segmentación e indexación.
* **Embeddings:** **OpenAI Embeddings** para el MVP; **proveedor local** en una etapa posterior.
* **PostgreSQL + `pgvector` en Servidor:** Datos transaccionales, fragmentos, vectores y trazabilidad.
* **Persistencia y consultas en Spring Boot:**
  * *Nota técnica importante:* En el documento base original se mencionó por error tipográfico `SprignBoot+ Pgvector.EntityFrameworkCore`. Como `EntityFrameworkCore` es exclusivo de .NET (C#), en nuestra arquitectura **100% Java + Spring Boot** se implementa con su equivalente nativo oficial: **Spring AI (`PgVectorStore` / `EmbeddingModel` / `ChatClient`) + Spring Data JPA / Hibernate Vector + `JdbcTemplate`**.
* **Motor RAG:** Búsqueda híbrida, recuperación contextual y generación de respuestas fundamentadas.

### Flujo de Indexación Obligatorio (Pasos 3 al 9)
1. **(Paso 3)** El cliente selecciona un PDF de su computador y lo envía cifrado por HTTPS.
2. **(Paso 4)** La API lo guarda temporalmente en el Servidor, con límites de tamaño, validación y escaneo de archivos.
3. **(Paso 5)** Un trabajo asíncrono extrae texto y ejecuta OCR para páginas escaneadas.
4. **(Paso 6)** El procesador divide el texto en fragmentos (**500–1.000 tokens con solapamiento moderado**), conservando **página, sección y orden**.
5. **(Paso 7)** Se solicita a OpenAI un embedding para cada fragmento.
6. **(Paso 8)** Se almacenan en PostgreSQL el **texto, vector, identificadores, permisos, modelo y metadatos**.
7. **(Paso 9)** **Se verifica la indexación y se elimina la copia temporal del PDF** según la política acordada. El PDF original permanece en el equipo del cliente.

### Flujo de Consulta Obligatorio (Pasos 10 al 14)
1. **(Paso 11)** Se genera el embedding de la pregunta con **el mismo modelo utilizado para el índice consultado**.
2. **(Paso 12)** PostgreSQL recupera fragmentos mediante `pgvector`, **siempre aplicando filtros de `tenant` y autorización**.
3. **(Paso 13)** Se combinan, cuando convenga, **resultados vectoriales y búsqueda textual**; se **reordenan y seleccionan evidencias**.
4. **(Paso 14)** El modelo recibe fragmentos recuperados y devuelve análisis con **citas al documento, página y fuente**.

### Limitaciones de No Conservar el PDF (Que el sistema debe gestionar explícitamente)
* La IA puede consultar fragmentos ya indexados con el PC apagado, pero no puede abrir, descargar ni verificar el PDF original si no está disponible.
* Las citas por página dependen de metadatos extraídos durante la indexación.
* Para **valor probatorio, fidelidad de imágenes, tablas, firmas o sellos**, el original puede ser indispensable; guardar hash no reemplaza el archivo.
* **Reindexar por cambio de OCR o extracción** puede exigir que el cliente vuelva a cargar el PDF.

---

## 2. Dominio del Proyecto Elegido: Gestor Inteligente de Licitaciones Médicas y Contratación / Auditoría en Salud (`MedTender RAG`)

### ¿De qué trata el proyecto?
Es una plataforma empresarial para **hospitales, clínicas, aseguradoras, laboratorios farmacéuticos y proveedores biomédicos** que gestionan y auditan **expedientes de licitaciones médicas y contratación en salud** (así como auditoría de documentación clínica/contractual asociada).

Un **Expediente** en este sistema agrupa documentos PDF críticos y pesados como:
* **Pliegos de condiciones hospitalarios** y contratos de suministro médico.
* **Adendas modificatorias** (que alteran requisitos técnicos, fechas o presupuestos del pliego original).
* **Anexos técnicos y fichas técnicas de equipos biomédicos / medicamentos.**
* **Cuadros de medicamentos, insumos y precios unitarios** (con códigos técnicos como `CUM`, `UNSPSC`, `ATC`, `CIE-10`, principios activos y concentraciones).
* **Registros sanitarios (INVIMA / FDA / EMA), pólizas y certificados de experiencia/historia escaneados** con sellos notariales o firmas médicas.

### ¿Por qué es vital no guardar los PDFs en el VPS?
1. **Confidencialidad y cumplimiento legal:** Las ofertas económicas farmacéuticas, fórmulas técnicas y anexos clínicos son altamente confidenciales y no deben residir permanentemente en un VPS externo.
2. **Ahorro del 90%+ en almacenamiento del VPS:** Los pliegos y anexos médicos pesan cientos de MB; al destruir el PDF tras extraer sus fragmentos y vectores, un VPS económico puede almacenar miles de expedientes.
3. **Consulta 24/7 con el PC apagado:** Los médicos auditores, ingenieros biomédicos y abogados pueden interrogar todo el expediente desde su celular o portátil aunque el computador de la oficina donde están los PDFs originales esté apagado.

---

## 3. Entorno de Desarrollo Local y Stack Tecnológico

### Entorno ya instalado en la máquina del usuario (Windows 11)
* **Java:** `JDK 26.0.2` (`C:\Program Files\Java\jdk-26.0.2`) — configurar `pom.xml` compatible (Java 21+ / Spring Boot 3.4+).
* **Build Tool:** `Apache Maven 3.9.16`.
* **Contenedores:** `Docker 29.8.0` (para PostgreSQL 16 + `pgvector`, ClamAV y Ollama).
* **Node.js:** `v24.14.0` (para el frontend React + Vite + TypeScript).

### Stack Técnico Exacto a Utilizar
* **Backend:** Java + **Spring Boot 3.4+**, Spring Web, Spring Security 6 (JWT stateless), Spring Data JPA, Flyway, `@Async` (`ThreadPoolTaskExecutor`).
* **IA y Persistencia Vectorial:** **Spring AI** (`EmbeddingModel`, `ChatClient`) + **Hibernate Vector / `JdbcTemplate`**.
  * *Fase 1 (MVP):* OpenAI (`text-embedding-3-small` de 1536 dimensiones + `gpt-4o-mini` / `gpt-4o`).
  * *Fase 2 (Local):* Proveedor local con Ollama / vLLM (`bge-m3`) mediante un **`EmbeddingRouter`**.
* **Base de Datos:** **PostgreSQL 16 + `pgvector`** (`pgvector/pgvector:pg16` en Docker) con índices **`HNSW`** (`vector_cosine_ops`) y **`GIN`** (`tsvector` con diccionario `'spanish'`).
* **Procesamiento de PDFs, Tablas, OCR y Tokens:**
  * **Apache Tika:** Validación de *Magic Bytes* reales (`application/pdf` / `%PDF-`).
  * **ClamAV** (o servicio enchufable de escaneo antivirus por socket TCP + fallback configurable en desarrollo).
  * **Apache PDFBox 3.x:** Extracción de texto nativo página por página y detección de imágenes/recursos incrustados (`PDImageXObject`).
  * **Tabula-java:** Detección de tablas (presupuestos, cuadros de medicamentos, laboratorios) y conversión automática a formato **Markdown Table** (`| Col1 | Col2 |`).
  * **Tess4J (Tesseract OCR):** OCR a 300 DPI en español (`spa`) **únicamente en las páginas escaneadas** (donde la densidad de texto nativo es menor a un umbral y hay imágenes).
  * **JTokkit:** Conteo exacto de tokens reales (`cl100k_base`) para segmentar entre **500 y 1.000 tokens** con **15% de solapamiento (~100 tokens)**.
* **Frontend Web:** **React + TypeScript + Vite + TailwindCSS + `pdfjs-dist`**:
  * Gestión de expedientes, subida temporal con barra de progreso del pipeline (`VALIDANDO` $\rightarrow$ `EXTRAYENDO_OCR` $\rightarrow$ `FRAGMENTANDO` $\rightarrow$ `VECTORIZANDO` $\rightarrow$ `INDEXADO_Y_PDF_ELIMINADO`).
  * Consola de Chat RAG con citas clicables, alertas probatorias y **Visor Local Desacoplado** usando la **`File System Access API`** del navegador + **`Web Crypto API` (`SHA-256`)** + **`PDF.js`**.

---

## 4. Diseño de Base de Datos (PostgreSQL 16 + `pgvector`)

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Tenants (Empresas / Hospitales / Aseguradoras)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre VARCHAR(150) NOT NULL,
    nit VARCHAR(50) UNIQUE NOT NULL,
    politica_borrado VARCHAR(30) NOT NULL DEFAULT 'INMEDIATO', -- INMEDIATO | DIFERIDO_1H
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Usuarios
CREATE TABLE usuarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(150) NOT NULL,
    rol_global VARCHAR(40) NOT NULL, -- ADMIN_TENANT, JURIDICO, AUDITOR_MEDICO, BIOMEDICO, LECTOR
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Expedientes de Licitación Médica / Auditoría
CREATE TABLE expedientes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    codigo_expediente VARCHAR(80) NOT NULL,
    titulo VARCHAR(250) NOT NULL,
    entidad_contratante VARCHAR(200),
    tipo_expediente VARCHAR(50) NOT NULL, -- LICITACION_MEDICAMENTOS, DOTACION_BIOMEDICA, AUDITORIA_CLINICA
    estado VARCHAR(40) NOT NULL DEFAULT 'ABIERTO',
    embedding_model_activo VARCHAR(80) NOT NULL DEFAULT 'text-embedding-3-small',
    embedding_dimension INT NOT NULL DEFAULT 1536,
    created_by UUID NOT NULL REFERENCES usuarios(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, codigo_expediente)
);

-- 4. Permisos granulares por Expediente
CREATE TABLE expediente_permisos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    expediente_id UUID NOT NULL REFERENCES expedientes(id) ON DELETE CASCADE,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    permiso VARCHAR(30) NOT NULL, -- LECTOR, EDITOR, ADMIN
    UNIQUE (expediente_id, usuario_id)
);

-- 5. Documentos Indexados (Trazabilidad del PDF que NO se conserva en el VPS)
CREATE TABLE documentos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    expediente_id UUID NOT NULL REFERENCES expedientes(id) ON DELETE CASCADE,
    nombre_archivo_original VARCHAR(255) NOT NULL,
    tipo_documento VARCHAR(50) NOT NULL, -- PLIEGO, ADENDA, FICHA_TECNICA, REGISTRO_SANITARIO, HISTORIA_CLINICA, PRESUPUESTO
    numero_adenda INT DEFAULT 0, -- > 0 si es una adenda modificatoria
    sha256_original CHAR(64) NOT NULL,
    tamano_bytes BIGINT NOT NULL,
    total_paginas INT,
    estado_indexacion VARCHAR(40) NOT NULL, -- RECIBIDO, VALIDANDO, PROCESANDO_OCR, VECTORIZANDO, INDEXADO_Y_PURGADO, ERROR_PURGADO
    ocr_version VARCHAR(30) NOT NULL DEFAULT 'tesseract-5.x-v1',
    extractor_version VARCHAR(30) NOT NULL DEFAULT 'pdfbox-3.x-tabula-v1',
    embedding_model VARCHAR(80) NOT NULL,
    total_chunks_esperados INT DEFAULT 0,
    total_chunks_guardados INT DEFAULT 0,
    temp_file_purged BOOLEAN NOT NULL DEFAULT FALSE,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    purged_at TIMESTAMPTZ
);

-- 6. Fragmentos (Chunks + Vectores + Texto Completo + Metadatos)
CREATE TABLE fragmentos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    expediente_id UUID NOT NULL REFERENCES expedientes(id) ON DELETE CASCADE,
    documento_id UUID NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    orden INT NOT NULL, -- Orden secuencial dentro del documento (1, 2, 3...)
    pagina_inicio INT NOT NULL,
    pagina_fin INT NOT NULL,
    seccion VARCHAR(255) NOT NULL,
    contenido_texto TEXT NOT NULL,
    contenido_vectorizado TEXT NOT NULL, -- Incluye la cabecera contextual inyectada
    token_count INT NOT NULL,
    embedding_model VARCHAR(80) NOT NULL,
    embedding vector(1536) NOT NULL,
    fts_vector tsvector GENERATED ALWAYS AS (to_tsvector('spanish', coalesce(seccion, '') || ' ' || coalesce(contenido_texto, ''))) STORED,
    metadata_jsonb JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- metadata_jsonb guarda:
    -- {
    --   "extraction_method": "NATIVE" | "OCR" | "MIXED",
    --   "ocr_confidence": 0.94,
    --   "has_tables": true,
    --   "has_visual_elements": true,
    --   "has_signatures_or_stamps": true,
    --   "tipo_documento": "ADENDA",
    --   "numero_adenda": 2
    -- }
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (documento_id, orden)
);

-- Índices críticos para rendimiento y seguridad Multi-Tenant
CREATE INDEX idx_fragmentos_tenant_expediente ON fragmentos (tenant_id, expediente_id);
CREATE INDEX idx_fragmentos_doc_orden ON fragmentos (documento_id, orden);
CREATE INDEX idx_fragmentos_fts ON fragmentos USING GIN (fts_vector);
CREATE INDEX idx_fragmentos_embedding_hnsw ON fragmentos USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
```

---

## 5. Detalles de Ingeniería que el Sistema DEBE Implementar

### A. Ingesta Efímera y Borrado Garantizado (Pasos 3, 4 y 9)
1. El PDF entra por `MultipartFile` bajo HTTPS.
2. Se valida tamaño máximo, firma binaria `%PDF-` con **Apache Tika**, ausencia de contraseña (`PDDocument.isEncrypted()`) y escaneo antivirus.
3. Se calcula el **`SHA-256`** en streaming y se guarda temporalmente en una ruta aislada (`/tmp/medtender-ephemeral/{uuid}.pdf`).
4. **Verificación previa al borrado:** Al terminar la vectorización, el sistema comprueba en PostgreSQL que `total_chunks_esperados > 0`, que `COUNT(fragmentos WHERE documento_id = :docId AND embedding IS NOT NULL) == total_chunks_esperados` y confirma la transacción.
5. **Borrado físico y Acta de Purga:** En un bloque garantizado (`finally` + `@Scheduled` de barrido de huérfanos), ejecuta `Files.deleteIfExists(tempPath)` y actualiza en `documentos`: `temp_file_purged = true`, `purged_at = NOW()`, `estado_indexacion = 'INDEXADO_Y_PURGADO'`.

### B. Extracción Híbrida por Página, Tablas a Markdown y Chunking (Pasos 5 y 6)
1. **Análisis página a página:**
   * Si la página tiene texto nativo suficiente (`texto.trim().length() >= 60`), **PDFBox** extrae el texto y **Tabula-java** detecta tablas (cuadros de medicamentos, precios o paraclínicos) convirtiéndolas en **Tablas Markdown**.
   * Si la página tiene casi cero texto nativo y contiene imágenes grandes, se rasteriza **solo esa página** a 300 DPI con `PDFRenderer` y se procesa con **Tesseract OCR**, guardando `ocr_confidence`.
   * Si PDFBox detecta imágenes incrustadas relevantes (sellos, firmas, planos, gráficas o imágenes diagnósticas), marca `has_visual_elements = true` y `has_signatures_or_stamps = true` en `metadata_jsonb`.
2. **Chunking de 500–1.000 tokens con `JTokkit`:**
   * Se detectan encabezados de sección (`CAPÍTULO`, `NUMERAL`, `CLÁUSULA`, `ADENDA`, `SECCIÓN`, `FICHA TÉCNICA`, `ANTECEDENTES`).
   * Se corta el texto en fragmentos de **500 a 1.000 tokens reales** con un **solapamiento del 15% (~100 tokens)**, asignando `orden = 1, 2, 3...`, `pagina_inicio`, `pagina_fin` y `seccion`.
3. **Cabecera Contextual antes de Vectorizar (Paso 7):**
   * Antes de pedir el embedding, se forma `contenido_vectorizado`:
     `[Expediente: {codigo} | Doc: {nombre} | Tipo: {tipo} | Pág: {p_ini}-{p_fin} | Sección: {seccion}] {contenido_texto}`.

### C. Consistencia de Modelo con `EmbeddingRouter` y Re-vectorización sin PDF (Pasos 7 y 11)
1. **`EmbeddingRouter`:** Antes de ejecutar una consulta sobre un expediente, consulta el campo `embedding_model_activo` de ese expediente (ej. `text-embedding-3-small` de OpenAI o `bge-m3` de Ollama local) y genera el embedding de la pregunta con **exactamente ese mismo proveedor**.
2. **Migración a proveedor local sin pedir el PDF:** Como la columna `contenido_vectorizado` sí se conserva en PostgreSQL, si el cliente decide pasar de OpenAI a un modelo local en la Etapa 2, un servicio de migración lee el texto de PostgreSQL y recalcula los embeddings **sin necesitar el PDF original**.
3. **Control de versión de OCR:** Si en el futuro cambia el motor OCR (`ocr_version`), el sistema identifica los documentos escaneados con versión antigua y muestra un aviso en la UI por si el cliente desea volver a seleccionarlos desde su PC.

### D. Búsqueda Híbrida SQL (RRF), Recuperación Contextual por `orden` y Reranking (Pasos 12 y 13)
1. **Seguridad primero:** Toda consulta verifica que el usuario tenga permiso en `expediente_permisos` y filtra en SQL por `WHERE f.tenant_id = :tenantId AND f.expediente_id = :expedienteId`.
2. **Fusión Recíproca de Rangos (RRF) en PostgreSQL:**
   * Combina en una sola consulta SQL el **Top 20 Vectorial** (`embedding <=> CAST(:queryVector AS vector)`) con el **Top 20 Léxico** (`ts_rank_cd(fts_vector, websearch_to_tsquery('spanish', :queryText))`, ideal para códigos exactos como `UNSPSC`, `CUM`, `INVIMA`, `CIE-10`, números de resolución o `Adenda 02`).
3. **Expansión Contextual por `orden`:**
   * Para los fragmentos con mayor puntaje, recupera sus vecinos inmediatos (`orden - 1` y `orden + 1`) del mismo `documento_id` para evitar cláusulas o tablas cortadas a la mitad.
4. **Reranking de Dominio:**
   * Da un *boost* de prioridad a los fragmentos cuyo documento sea `tipo_documento = 'ADENDA'` (ordenados por `numero_adenda DESC`), para advertir siempre si una adenda modificó un requisito del pliego original.

### E. Generación Fundamentada con Citas y Visor Local del PDF Original (Paso 14 y Limitaciones)
1. **Salida Estructurada (JSON):** El motor RAG devuelve:
   * `respuestaAnalitica`: Respuesta clara y fundamentada (o abstención explícita si no hay evidencia en los fragmentos).
   * `citas`: Lista de objetos con `documentoId`, `nombreArchivo`, `tipoDocumento`, `sha256Original`, `paginaInicio`, `paginaFin`, `seccion`, `orden`, `extractoLiteral`, `metodoExtraccion` (`NATIVE` / `OCR`), `confianzaOcr`, `requiereVerificacionVisualOriginal` (`true/false`) y `motivoVerificacionVisual` (ej. *"Contiene sellos/firmas, tablas o imágenes que requieren verificar el PDF original en su PC"*).
2. **Visor Local en el Navegador (Cuando el PC del cliente está encendido):**
   * El frontend incluye un botón **"Vincular Carpeta Local de PDFs"** usando la **`File System Access API`** (`window.showDirectoryPicker()`).
   * Cuando el usuario hace clic en una cita (ej. `[Pliego_Hospital.pdf, Pág. 24]`), el navegador busca el archivo en la carpeta local, calcula su **`SHA-256`** con `crypto.subtle.digest('SHA-256', buffer)`, verifica que coincida con el `sha256Original` guardado en el VPS y lo abre directamente en la **página 24** usando `PDF.js` 100% en memoria local, **sin subir el archivo al servidor**.

---

## 6. Plan de Ejecución por Sprints (Orden en que debes construirlo)

* **Sprint 1 — Infraestructura, Seguridad Multi-Tenant y Expedientes:**
  * `docker-compose.yml` (`pgvector/pgvector:pg16`), `pom.xml`, migraciones Flyway (`V1__init_schema.sql`), autenticación JWT con `tenant_id` y CRUD de Expedientes + Permisos.
* **Sprint 2 — Ingesta Efímera HTTPS, Validación, `SHA-256` y Purga Garantizada:**
  * Endpoint `POST /api/v1/expedientes/{id}/documentos`, validación con Apache Tika y ClamAV/Scanner, guardado temporal, máquina de estados y borrado físico verificado con Acta de Purga (`purged_at` + `SHA-256`).
* **Sprint 3 — Procesamiento Asíncrono: PDFBox, Tablas a Markdown, OCR Selectivo y Chunking (`500–1.000` tokens):**
  * Extractor página a página, Tabula-java para tablas a Markdown, OCR selectivo con Tesseract, detector de elementos visuales/firmas y segmentador con `JTokkit` (500–1.000 tokens, 15% overlap, guardando `página`, `sección` y `orden`).
* **Sprint 4 — Vectorización en `pgvector` y `EmbeddingRouter` (OpenAI + Local):**
  * Inyección de cabecera contextual, persistencia de vectores en `pgvector` (`HNSW`), implementación del `EmbeddingRouter` (OpenAI MVP / Ollama Local) y endpoint de re-vectorización desde texto sin re-subir el PDF.
* **Sprint 5 — Motor RAG Híbrido (RRF), Priorización de Adendas, Citas y Frontend Web con Visor Local:**
  * Consulta SQL híbrida (`pgvector` + `tsvector` + RRF), expansión de contexto por `orden`, generación estructurada con citas y alertas probatorias, y aplicación web React + TypeScript con el visor local `File System Access API` + `PDF.js`.
