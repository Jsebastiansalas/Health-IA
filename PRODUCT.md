# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Auditores médicos, ingenieros biomédicos y abogados de entidades de salud (hospitales, aseguradoras) que revisan expedientes de licitaciones médicas: pliegos de condiciones, adendas, fichas técnicas, registros sanitarios, presupuestos e historias clínicas. Trabajan con muchos PDF, a veces escaneados, y necesitan respuestas con cita verificable. Sus documentos son confidenciales: no quieren subir los originales a un servidor ajeno. Entran desde un navegador de escritorio (Chrome o Edge), a veces desde tableta; consultan a cualquier hora.

## Product Purpose
MedTender es un asistente de IA para el sector salud (clínicas, hospitales, aseguradoras): permite consultar y analizar licitaciones médicas, historias clínicas y auditorías, y consultar medicamentos de Colombia con datos abiertos de INVIMA. Cada respuesta se fundamenta en los documentos del expediente y llega con la cita exacta (documento, página, extracto literal). Éxito: el usuario obtiene una respuesta fundamentada y comprueba la fuente abriendo el original desde su propio equipo. El tratamiento de la información (los PDF no se conservan en el servidor tras indexarlos, con verificación y acta de purga) es una garantía de apoyo, no el mensaje principal.

## Health Assistant Scope (sprints 24-29)
Además de las organizaciones, **pacientes y familias con cuenta personal** suben lo que reciben en el hospital (historia clínica, resultados, órdenes, fotos JPG/PNG/HEIC, informes de radiografía) y el asistente lo **explica** («Explícame este documento», en dos capas: lo que dice, con cita literal, y qué significan los términos, aparte y rotulado) e **informa** sobre medicamentos con fuente (prospectos subidos y fichas técnicas oficiales). **Nunca diagnostica, receta ni dosifica**: esas peticiones se rechazan con una regla de código que remite al médico o farmacéutico, sin depender del modelo; una posible urgencia antepone siempre el aviso de llamar al 123. Las imágenes médicas no se interpretan: de una radiografía solo se lee el informe del radiólogo. El texto sale a la nube (Gemini) anonimizado y con consentimiento informado; el usuario puede borrar su historial y su cuenta. Revisión legal pendiente antes de abrirlo a pacientes reales (Ley 1581 de 2012, Ley 2015 de 2020, software como dispositivo médico).

## Positioning
El asistente de IA para la salud que no inventa: responde sobre licitaciones médicas, historias clínicas y medicamentos con la fuente a la vista, y cuando los documentos no respaldan una respuesta, se abstiene de forma explícita. El visor abre el original desde la carpeta local del usuario comparando su SHA-256 con el registrado. La comunicación pública (portada, ingreso) habla de salud, de los casos de uso y de la confianza en la respuesta; la eliminación del PDF aparece solo como una garantía más dentro de «información de salud, tratada con cuidado».

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
