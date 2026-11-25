# Registro de cambios

Generado con `python infra/scripts/changelog.py`.

## Sin publicar (2026-11-25)

### Novedades
- sprint 43 (2/n) - rastreo de errores sin datos de salud, con GlitchTip autoalojado
- sprint 43 (1/n) - monitoreo con alertas por correo y panel; el respaldo fallido ya no se da por bueno
- sprint 42 - tus datos: descarga y retención, historial cifrado y respaldos fuera del equipo con restauración de prueba
- sprint 41 - IA de producción: Vertex AI, Claude de respaldo con cortacircuitos, costo con tope diario y consentimiento v4
- sprint 40 - cuentas seguras: sesiones revocables, contraseña olvidada y cambiada, política y dos pasos
- sprint 39 - recordatorios de controles que la persona confirma, con aviso neutro y calendario
- sprint 38 - preparar mi cita con resumen citado, preguntas editables y PDF en el navegador
- sprint 37 - línea de tiempo y evolución de resultados con cita en cada dato
- sprint 36 - MedTender como app instalable (PWA)
- tramos con entrada en cada escena del recorrido de la portada
- portada scroll-world completa con el motor de la skill y scroll suave con Lenis
- recorrido por el hospital movido por el scroll en las portadas
- rediseño completo «Registro clínico»: Geist y Phosphor, barra superior, banner del caso, tabla que colapsa a tarjetas, claro por defecto, dos portadas, páginas legales y 404
- sprint 35 - beta cerrada: paquete de revisión médica, guía de Cloudflare Tunnel, IP real detrás del túnel y hallazgos atribuidos al documento
- consentimiento v3 para la beta cerrada (Gemini gratuito, respaldos de 14 días, auditoría sin vencimiento, terceros y menores)
- glosario curado de 125 términos para la capa «qué significan» (deja de depender del modelo; pendiente de revisión profesional)
- sprint 33 (parte 2) - verificación de correo de cuentas personales: enlace de un solo uso, reenvío limitado y bloqueo hasta confirmar (V12)
- sprint 33 (parte 1) - prospectos subidos como fuente del cruce, CIMA apagado por defecto y enlaces a fuentes oficiales
- sprint 32 - cruce de los medicamentos de tus documentos con sus fichas técnicas, con citas a ambos lados y sin recomendar ni dosificar
- sprint 31 - garantías deterministas: paráfrasis comprobada contra el fragmento, posología sin respaldo sustituida y corpus de límites clínicos
- sprint 30 - verificación con Gemini, Tesseract y stack reales; avisos de urgencia ampliados y arreglos de interfaz clínica
- sprint 29 - evaluación de seguridad: rechazo de dosis, recetas y diagnósticos sin modelo, casos adversos y cierre de documentación
- sprint 28 - efectos e interacciones de medicamentos con fuente: tipo PROSPECTO, fichas técnicas CIMA (sin posología) y reglas que prohíben dosificar o elegir por la persona (V11)
- sprint 27 - «Explícame este documento» en dos capas (lo que dice, con citas literales; qué significan los términos, aparte y rotulada); sin diagnosticar, recetar ni dosificar
- sprint 26 - fotos y escaneos de documentos (JPG, PNG, HEIC) con OCR, avisos de calidad y rechazo de imágenes sin texto (V10)
- sprint 25 - anonimización de datos personales antes de enviar texto a la nube; consentimiento v2
- sprint 24 - seguridad, consentimiento y cuentas personales (V9), avisos de salud y detector de urgencias
- frontend: el enfoque pasa a la salud (licitaciones médicas, historias clínicas y medicamentos), sin el mensaje del PDF eliminado
- sprint 23 - frontend: pulido (clases heredadas fuera, textos largos, objetivos táctiles)
- sprint 22 - frontend: portada e ingreso con el expediente en acción, sin montañas ni testimonios
- sprint 21 - frontend: índice de expedientes y tablas de fuentes en Medicamentos
- sprint 20 - frontend: la cita como folio con texto resaltado y visor local acoplado
- sprint 19 - frontend: espacio de trabajo del expediente (cabecera compacta, riel de documentos, pipeline legible)
- sprint 18 - frontend: identidad «Expediente / folio», temas papel y nocturno, tokens semánticos y logotipo
- sprint 15 - verificación de modelos de IA al arrancar y límite de dimensión del router
- sprint 16 - evidencia probatoria estructurada y OCR con reintento (rotación y binarización)
- sprint 17 - endurecimiento: seed demo solo local, rotación de secretos y verificar.ps1
- sprint 14 - aislamiento de tenants en la base con RLS (V8) y rol medtender_app
- medicamentos de Colombia con datos abiertos de INVIMA (V7)
- rediseño del frontend: paleta Geist/Inter, montañas y componentes redondeados
- sprint 12 - rediseño del frontend: negatoscopio, tema oscuro
- sprint 11 - rediseño del frontend: microscopio e histología, tema claro
- sprint 10 (parcial) - integración Java + agente en Docker, renombre a agente/
- sprint 9 - Python como agente interno y proxy de IA en Java
- sprint 8 - expedientes, permisos e ingesta efímera en Java
- sprint 7 - núcleo Java (Spring Boot): esquema Flyway, JWT, usuarios, límites y auditoría
- sprint 6 - observabilidad, límites, auditoría, respaldos y despliegue con HTTPS
- sprint 5 frontend - aplicación web con consola RAG y visor local de PDFs
- sprint 5 backend - motor RAG híbrido con RRF, adendas y citas verificables
- sprint 4 - vectorización con Gemini, EmbeddingRouter y re-vectorización sin PDF
- sprint 3 - procesamiento asíncrono, extracción, OCR selectivo y chunking
- sprint 2 - ingesta efímera, validación, SHA-256 y purga garantizada
- sprint 1 - infraestructura, seguridad multi-tenant y expedientes

### Correcciones
- en producción la API y los respaldos no tenían salida a internet
- Vertex con modelo, región y precios vigentes, y compose para el Docker local
- el consentimiento dice la verdad sobre el proveedor de IA que está activo
- revisión final del rediseño: tablas de medicamentos a tarjetas, banner del caso sin kicker y con la acción principal arriba, contraste AA, espaciados y radios dentro del sistema
- modelo LLM estable por defecto y sin reintentos sobre un modelo colgado

### Rendimiento
- sprint 43 (4/n) - portada liviana, PDF sin conversor de HTML y vista previa al compartir

### Documentación
- plan D (sprints 40–45): de beta cerrada a producción con pacientes reales
- sprint 34 - paquete para la revisión legal (mapa de datos, retención, supresión, consentimiento y preguntas al abogado)
- sprint 24 verificado (Java 87, Python 225, Vitest 24)
- sprint 13 - plan actualizado y desviaciones respecto a Requerimientos.md
