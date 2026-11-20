# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Auditores médicos, ingenieros biomédicos y abogados de entidades de salud (hospitales, aseguradoras) que revisan expedientes de licitaciones médicas: pliegos de condiciones, adendas, fichas técnicas, registros sanitarios, presupuestos e historias clínicas. Trabajan con muchos PDF, a veces escaneados, y necesitan respuestas con cita verificable. Sus documentos son confidenciales: no quieren subir los originales a un servidor ajeno. Entran desde un navegador de escritorio (Chrome o Edge), a veces desde tableta; consultan a cualquier hora.

## Product Purpose
MedTender permite consultar y analizar el contenido de expedientes de licitación sin entregar los PDF originales. El servidor guarda solo fragmentos de texto, embeddings y metadatos; cada PDF se elimina tras indexarlo, con verificación y un acta de purga. Éxito: el usuario obtiene una respuesta fundamentada con la cita exacta (documento, página, extracto literal) y comprueba la fuente abriendo el original desde su propio equipo, sin que el archivo se suba.

## Positioning
Respuestas con citas verificables sobre documentos que nunca quedan en el servidor: el PDF se borra tras indexar y el visor abre el original desde la carpeta local del usuario comparando su SHA-256 con el registrado. Cuando no hay evidencia, la respuesta es una abstención explícita, no una conjetura.

## Operating Context
Organización multi-tenant: cada organización ve solo lo suyo; un expediente ajeno responde «no encontrado». Roles: ADMIN_TENANT, JURIDICO, AUDITOR_MEDICO, BIOMEDICO y LECTOR; permisos por expediente LECTOR < EDITOR < ADMIN. Flujo: crear expediente → subir PDF (tipo de documento, número de adenda) → pipeline (VALIDANDO → EN_COLA → EXTRAYENDO_OCR → FRAGMENTANDO → VECTORIZANDO → INDEXADO_Y_PURGADO) → consultar con citas → abrir el original local. Las adendas pesan más que el pliego base y se señalan como alerta de modificación.

## Capabilities and Constraints
- Interfaz en español (es-CO). Contrato de API `/api/v1/**` fijo (Spring Boot); el frontend no cambia datos ni rutas.
- Visor local: File System Access API (solo Chrome/Edge sobre HTTPS o localhost), con respaldo manual en otros navegadores; el archivo nunca se sube.
- CSP estricta en producción: sin CDN de terceros (fuentes e iconos empaquetados), `img-src 'self' data: blob:`.
- Sin evidencia real: no existen clientes, testimonios ni estadísticas de uso todavía.
- Por decisión del dueño, la bienvenida puede incluir cifras y testimonios de EJEMPLO, siempre marcados como ficticios y a reemplazar antes de publicar.

## Brand Commitments
Nombre: MedTender. Logotipo: un folio con la esquina doblada, una «M» a tinta y el resaltador por debajo (rediseñado en el sprint 18). Decisión del dueño (20-nov-2026, reemplaza el estilo oscuro azul-turquesa anterior): dirección «Expediente / folio», con DOS temas, papel (día, por defecto) y nocturno, que siguen el sistema operativo y se pueden fijar a mano. Decoración original hecha en código, nunca imágenes de stock; página de bienvenida antes del ingreso.

## Evidence on Hand
Ninguna real: sin clientes, casos, prensa ni métricas. Existe un PDF de prueba sintético (`Pliego_E2E.pdf`) y cuentas de demostración en desarrollo. Todo contenido de demostración debe etiquetarse como ejemplo.

## Product Principles
1. La confianza se demuestra: cada afirmación de la interfaz apunta a una fuente que el usuario puede abrir y verificar.
2. La privacidad es el mecanismo, no una cláusula: el momento en que el PDF se elimina se hace visible.
3. Abstenerse es una respuesta válida: la interfaz nunca disfraza la falta de evidencia.
4. Lo difícil queda a la vista (estados del pipeline, rechazos, avisos de OCR), con lenguaje claro en vez de códigos.
5. Herramienta de trabajo diario: rápida, escaneable y accesible incluso con decoración.

## Accessibility & Inclusion
Contraste AA, navegación completa por teclado, `prefers-reduced-motion` respetado (el fondo animado se vuelve estático), textos en español claro para público profesional no técnico.
