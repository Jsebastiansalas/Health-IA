# Paquete para la revisión legal de MedTender

> **Qué es esto.** Un inventario técnico, escrito por el equipo de desarrollo, de qué datos trata MedTender, adónde van, cuánto tiempo se conservan y cómo se borran. **No es asesoría legal ni afirma que el producto cumpla ninguna norma.** Sirve para que un abogado (o la autoridad de protección de datos) revise el producto sin tener que leer el código. Todo lo que dice «por confirmar» necesita decisión de quien lo revise. Estado: 23-nov-2026, `develop` tras el sprint 33.

## 1. Qué hace el producto (en una frase)
Una persona (paciente o familiar, con cuenta propia) o una organización sube documentos de salud (historia clínica, resultados, órdenes, fotos, informes de radiografía, prospectos). El asistente los **explica y cita**; no diagnostica, no receta y no indica dosis (esas peticiones se rechazan con reglas de código, `agente/app/rag/seguridad.py`).

## 2. Datos que se tratan

| Categoría | Qué contiene | Dónde queda | Sensibilidad |
|---|---|---|---|
| Cuenta | Nombre, correo, hash bcrypt de la contraseña (nunca la contraseña), tipo de cuenta, confirmación de correo (solo hash del token) | Base de datos (`usuarios`, `verificaciones_correo`) | Personal |
| Documentos | **Texto completo extraído** de cada documento, troceado en fragmentos con su página; incluye nombres, cédulas, diagnósticos, resultados | Base de datos (`fragmentos.contenido_texto`, **sin enmascarar**, para poder citar literal) | **Sensible (salud)** |
| Texto «vectorizado» | El mismo texto con los datos personales etiquetados enmascarados (`[PERSONA_1]`…) | Base de datos (`fragmentos.contenido_vectorizado`) y vectores de embeddings | Sensible, reducido |
| Archivo original (PDF/foto) | El documento tal como se subió | **Disco efímero del servidor**: se elimina tras indexar (cuentas personales: inmediato; organizaciones: inmediato o a los 60 min según política). Queda un acta de purga con su SHA-256 | Sensible, transitorio |
| Lectura para la línea de tiempo | Los eventos con fecha y valores de laboratorio que la IA **propone** al leer cada documento (sin comprobar; la pantalla solo muestra lo que coincide con el texto) | Base de datos (`extracciones_linea`), cifrado con `DATOS_CLAVE`; se borra con el documento y sale en «Descargar mis datos» | Sensible |
| Consultas | La pregunta y la respuesta completa (con citas); las «explicaciones» y «cruces» se guardan sin el nombre del archivo | Base de datos (`consultas`) | Sensible |
| Consentimiento | Versión del texto aceptado y fecha | Base de datos (`consentimientos`) | Personal |
| Auditoría | Quién hizo qué, cuándo, con qué resultado, IP y correo; **nunca** el contenido de preguntas, documentos ni respuestas (solo ids y conteos) | Base de datos (`auditoria`, solo anexar; un trigger impide UPDATE/DELETE) | Personal |
| Límites de tasa | Contadores por IP/usuario (sin contenido) | Redis | Técnico |

## 3. Adónde va la información

| Destino | Qué sale | Protección aplicada | Pendiente |
|---|---|---|---|
| **Google Cloud (Vertex AI, Gemini)**, encargado; región configurable (`VERTEX_REGION`) | (a) texto de los fragmentos con datos personales **enmascarados por patrones**, para generar embeddings; (b) en cada consulta, explicación o cruce: la pregunta y los fragmentos relevantes enmascarados, con nombre de archivo neutro («documento-1»); (c) **al terminar de indexar** un documento de una cuenta personal, sin que la persona pida nada más: sus fragmentos enmascarados, para la línea de tiempo (se apaga con `CRONOLOGIA_AL_INDEXAR=false`) | Anonimización previa reversible solo en el servidor propio (`agente/app/privacidad/anonimizar.py`), interruptor `anonimizar_antes_de_nube` (activo por defecto), consentimiento informado previo (cuentas personales). Desde el sprint 41 el agente **no arranca en producción** con la API gratuita de AI Studio (`IA_PROVEEDOR=vertex` obligatorio) | Aceptar el DPA de Google Cloud (Cloud Data Processing Addendum), elegir la región y confirmar que Vertex no entrena con los datos ni los conserva más allá de su caché |
| **Anthropic (Claude)**, encargado en EE. UU., solo como respaldo si Vertex falla (`LLM_RESPALDO_PROVEEDOR=claude`) | Lo mismo que (b) y (c): la pregunta y los fragmentos enmascarados de una consulta, explicación o cruce, y los de un documento al leerlo para la línea de tiempo. No recibe texto para embeddings | La misma anonimización previa; solo se usa cuando el principal falla o está saturado | Aceptar el DPA comercial de Anthropic y revisar su plazo de retención de las solicitudes a la API |
| Servidor SMTP (proveedor de correo por elegir) | Correo electrónico de la persona y un enlace de un solo uso | Enlace de un solo uso, vence en 24 h, solo se guarda su hash | Elegir proveedor y revisar sus condiciones |
| Nadie más | Tesseract (OCR) y ClamAV (antivirus) corren dentro del mismo servidor | — | — |

**Límite de la anonimización (declarado también en el consentimiento):** solo se enmascaran datos personales que aparecen *con etiqueta* («Paciente:», «CC», «Teléfono:», «Correo:»…). Un nombre suelto dentro de una frase puede no detectarse y viajar al proveedor de IA. Los números sin etiqueta (CUM, INVIMA, NIT) no se tocan a propósito.

## 4. Conservación y supresión

| Dato | Cuánto se conserva | Cómo se borra |
|---|---|---|
| Archivo original | Hasta terminar de indexar (inmediato) o 60 min (política diferida, solo organizaciones) | Automático; acta de purga con huella |
| Fragmentos, vectores, consultas | Hasta que la persona los borre. Las **consultas** (preguntas, respuestas, explicaciones, líneas de tiempo) además pueden vencer solas si la persona elige 3, 6, 12 o 24 meses en «Mis datos» (por defecto no vencen) | Botón «Borrar historial de preguntas», plazo de «Mis datos» y «Eliminar mi cuenta»; una organización elimina por expediente |
| Cuenta personal | Hasta que la persona la elimine | `POST /api/v1/cuenta/eliminar` (pide la contraseña): borra expedientes, documentos, fragmentos, consultas, consentimientos, verificaciones, usuarios y el espacio personal |
| Auditoría | **Sin fecha de vencimiento** (diseñada para sobrevivir al borrado) | No se borra al eliminar la cuenta: conserva correo, IP e ids. **Por confirmar**: si debe anonimizarse o vencer |
| **Respaldos de la base** | **Máximo 14 días**, dentro y fuera del equipo, cifrados con AES-256 (`BACKUP_PASSPHRASE`) | Vencen solos al hacerse una copia nueva; si las copias dejan de correr, la limpieza también. **Una cuenta eliminada sigue en los respaldos hasta 14 días** |
| Registros del servidor (logs) | Según la configuración de despliegue | Por definir; no contienen preguntas ni documentos |

**Acceso y portabilidad:** una cuenta personal descarga desde «Mis datos» un ZIP con su información (JSON y versión legible), con su contraseña y dejando constancia en la auditoría sin contenido. No incluye los archivos originales (se eliminan). En una organización lo gestiona la institución.

**Copia fuera del equipo (si el dueño la activa):** un proveedor de almacenamiento (p. ej. Backblaze B2 o Cloudflare R2, por decidir) recibiría los respaldos **ya cifrados**, sin la frase para abrirlos. **Por decidir con el abogado:** si es un encargado que deba nombrarse en el consentimiento y la política (hoy el texto no lo nombra), su país y su acuerdo. El versionado y el bloqueo de objetos del bucket deben quedar desactivados para que se cumplan los 14 días.

## 5. Medidas de seguridad implementadas
- **Aislamiento por persona/organización en la base** (Row Level Security con rol sin privilegios; una consulta de otro tenant devuelve «no encontrado»); probado en la suite y en una copia de datos reales.
- Autenticación con tokens de vida corta, límites de intentos y de consultas, verificación de correo de las cuentas personales (obligatoria en `docker-compose.prod.yml`).
- Todo el tráfico público pasa por Caddy con HTTPS; solo Caddy publica puertos; respuestas con `Cache-Control: no-store`.
- Antivirus (ClamAV) y validación del contenido real del archivo (no de su extensión) antes de procesar.
- Prompt-injection: el contenido de los documentos se trata como datos; lo que devuelve el modelo se acota por esquema y por verificación de citas.
- Secretos fuera del repositorio, rotación documentada (README, «Rotación de secretos»).

- **Cifrado en reposo:** las preguntas y respuestas guardadas van cifradas en la base (AES-256-GCM, clave fuera de la base). **El texto de los documentos no se cifra en la base** (la búsqueda lo necesita); lo protege el cifrado del disco, que es un requisito de despliegue que el dueño debe activar y que no protege frente a quien acceda al sistema en marcha.
- Cada 30 días se restaura de prueba el último respaldo y se comprueba el aislamiento entre cuentas.

- **Rastreo de errores y monitoreo (opcionales, autoalojados):** GlitchTip recibe solo el tipo de error y el punto del código, sin mensajes, usuarios, direcciones ni IP; las alertas por correo llevan solo nombres de servicios y cifras. Si se usara un servicio de rastreo o de correo de un tercero, habría que añadirlo a los encargados.

## 6. Textos que ve la persona (para revisar)
**Consentimiento informado** (`frontend/src/componentes/Consentimiento.tsx`) — la persona debe aceptarlo antes de subir o consultar. El punto 3 depende del proveedor de IA que esté activo, y cada texto tiene su versión (`ConsentimientoService.java`); al cambiar de proveedor hay que aceptarlo de nuevo. Abajo va la lista con el texto de producción (`2026-11-v5-claude`); las otras tres variantes del punto 3 están después y también hay que revisarlas.
1. MedTender está en pruebas cerradas: puede equivocarse. Compara siempre con tu médico o tu farmacéutico antes de decidir algo sobre tu salud.
2. Subirás documentos médicos (historias clínicas, resultados, órdenes, prospectos). Son datos sensibles. Si subes documentos de otra persona, declaras que tienes derecho a hacerlo o su autorización. Si eres menor de edad, usa esta cuenta con un adulto responsable.
3. Para leerlos y responderte usamos servicios de inteligencia artificial de terceros: Gemini en Google Cloud (Vertex AI) y, solo si ese servicio falla, Claude de Anthropic. Pueden procesar la información fuera de Colombia. Ninguno de los dos usa lo que les enviamos para entrenar sus modelos. Aun así, sube solo lo que necesites.
4. Antes de enviarle el texto ocultamos nombres, cédulas, teléfonos, correos y direcciones cuando aparecen con una etiqueta (por ejemplo «Paciente:» o «CC»). Este ocultamiento no es perfecto: un nombre suelto dentro de una frase puede no detectarse.
5. El archivo original se elimina del servidor después de leerlo. Guardamos fragmentos de texto tal como aparecen en el documento (con tus datos) y tus preguntas, para poder responderte y citar el texto exacto.
6. Puedes borrar tu historial de preguntas y eliminar tu cuenta con todo su contenido cuando quieras. Las copias de seguridad conservan los datos hasta 14 días más. El registro de accesos (tu correo, la fecha y tu dirección IP, nunca el contenido de tus documentos ni de tus preguntas) se conserva sin fecha de vencimiento.
7. MedTender explica y cita lo que dicen tus documentos. No es un médico, no diagnostica, no receta ni indica dosis. Si es una urgencia, llama al 123.

**Las otras variantes del punto 3:**
- `2026-11-v3` (API gratuita de Gemini, la de la beta actual): «Para leerlos y responderte usamos un servicio de inteligencia artificial de un tercero: Google Gemini, que puede procesar la información fuera de Colombia. En esta etapa usamos su versión gratuita, y Google puede conservar y usar lo que se le envía para mejorar sus productos. Por eso sube solo lo que necesites.»
- `2026-11-v3-claude` (API gratuita con Claude de respaldo): el texto anterior más «Si Gemini falla, tu pregunta y fragmentos de tus documentos pueden ir a Claude, de Anthropic, otra empresa que no usa lo que le enviamos para entrenar sus modelos.»
- `2026-11-v5` (Vertex AI sin respaldo): «Para leerlos y responderte usamos un servicio de inteligencia artificial de un tercero: Gemini en Google Cloud (Vertex AI), que puede procesar la información fuera de Colombia. Google no usa lo que le enviamos para entrenar sus modelos. Aun así, sube solo lo que necesites.»

Los textos no afirman que ya exista un contrato firmado: los acuerdos de tratamiento de datos con Google Cloud y Anthropic siguen pendientes (sección 3). La afirmación de que no entrenan con los datos se apoya en las condiciones de servicio de pago de cada proveedor y **hay que confirmarla**.

Además, si se configuran `VITE_RESPONSABLE` y `VITE_CONTACTO_PRIVACIDAD` al construir la web, la pantalla muestra «Responsable del tratamiento: … · contacto: …».

**Aviso permanente** (en las pantallas de consulta): «Información de apoyo, no atención médica. Explica y cita lo que dicen tus documentos y las fuentes; no diagnostica ni receta, y no sustituye a un profesional de la salud. En una urgencia, llama al 123.»

**Qué falta en esos textos (a decidir con el abogado):** el nombre y el contacto reales del responsable (hoy se configuran por variable y, si no están, la línea no aparece); que cada variante del punto 3 coincida con las condiciones y acuerdos de cada proveedor el día que se publique; texto para el caso de que la persona sea una institución; política de tratamiento y aviso de privacidad completos con enlace desde esta pantalla; términos y condiciones.

## 7. Límites conocidos del producto (para no prometer de más)
- La anonimización por patrones no es perfecta (sección 3).
- El texto de cada hallazgo de una explicación se comprueba por cifras y juicios, no por todo su significado; por eso la cita literal va al lado.
- El rechazo de dosis, recetas y diagnósticos usa reglas simples: cubre un corpus de 57 frases y prefiere el falso positivo, pero no toda redacción posible.
- El OCR de fotos puede equivocarse (se vio «lbuprofeno» por «Ibuprofeno»); los resultados de fotos llevan aviso de verificar el original.
- El detector de urgencias es por reglas; no garantiza detectar toda urgencia (se encontró y corrigió un caso, «me falta el aire»).
- La información de medicamentos viene de los prospectos que sube la persona y de enlaces a fuentes oficiales; las fichas de CIMA están apagadas por no tener confirmadas sus condiciones de reutilización.
- No se interpretan imágenes médicas; de una radiografía solo se lee el informe escrito.
- Probado con Gemini y Tesseract reales con documentos inventados; **no probado con pacientes reales** ni con fotos de teléfonos reales (HEIC de iPhone).

## 8. Preguntas para el abogado
1. **Protección de datos personales (Ley 1581 de 2012 y normas que la reglamentan, por confirmar):** los datos de salud son sensibles. ¿Es válida la autorización que da el consentimiento de la sección 6? ¿Qué debe decir la política de tratamiento y el aviso de privacidad? ¿Hay que registrar bases de datos ante la autoridad (RNBD)? ¿Quién es responsable y quién encargado del tratamiento?
2. **Transferencia internacional:** el envío de texto a Google (EE. UU.) ¿exige autorización específica o contrato de transmisión? ¿Qué cláusulas pedir al proveedor (no entrenamiento, ubicación, subencargados)?
3. **Historia clínica (Ley 2015 de 2020 y normas de historia clínica, por confirmar):** ¿aplican a una herramienta donde la persona sube *copias* de sus documentos? ¿Cambia algo si el usuario es una institución prestadora (cuentas de organización)?
4. **Software como dispositivo médico (regulación INVIMA de dispositivos médicos, por confirmar):** el producto explica documentos y **no** diagnostica ni recomienda tratamiento. ¿Basta esa delimitación y el aviso permanente para quedar fuera de la regulación? ¿Qué frases del producto podrían contar como finalidad médica?
5. **Supresión:** ¿es aceptable que la auditoría conserve correo e IP sin vencimiento y que los respaldos retengan los datos 14 días? ¿Qué plazos fijar?
6. **Menores de edad y terceros:** una persona sube documentos de otra (un hijo, un familiar). ¿Qué debe declarar quien los sube?
7. **Responsabilidad:** términos y condiciones, límites de responsabilidad y manejo de incidentes (¿plazo de notificación de una brecha?).
8. **Publicidad y marca:** ¿qué se puede decir en la portada sin sugerir atención médica?
9. **Lectura al subir:** cada documento de una cuenta personal se envía a la IA al indexarlo y se guarda lo que propone. El consentimiento dice «Para leerlos y responderte usamos un servicio de inteligencia artificial», y su punto 5 habla de guardar fragmentos y preguntas, no este dato derivado (sí lo dice la página de privacidad). ¿Basta, o hay que nombrarlo en el consentimiento y pedir que se acepte de nuevo?

## 9. Cómo comprobar lo dicho aquí
- Mapa de datos y borrado: `api-java/src/main/java/co/medtender/api/privacidad/` y migraciones `V9`, `V12`.
- Lo que sale a Google: `agente/tests/test_privacidad_nube.py` (inspecciona el prompt exacto) y `agente/scripts/verificar_gemini_real.py` (Gemini real con documentos inventados).
- Aislamiento: `AislamientoRlsIT`; supresión: `PrivacidadIT`; verificación de correo: `VerificacionCorreoIT`.
- Límites y rechazos: `agente/tests/corpus_limites.py`, `test_seguridad*.py`, `test_garantias.py`.
