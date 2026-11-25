# Plan D: de beta cerrada a producción con pacientes reales (sprints 40–45)

Sale del diagnóstico de punta a punta del 25-nov-2026. El Plan C dejó un producto completo para una beta cerrada; este plan cierra lo que impide abrirlo a pacientes reales y lo sube de nivel. Rige el mismo flujo: un sprint por rama `feature/*`, resumen al final, «Integrar y seguir».

Orden por riesgo: primero lo que puede causar daño (cuentas, datos de salud en un modelo gratuito, pérdida de datos), después lo que permite operar con tranquilidad y medir, y al final lo que hace el producto mejor.

## Decisiones del dueño (antes o durante el plan)

| # | Decisión | Para qué sprint | Recomendación |
|---|---|---|---|
| D1 | Cuenta de Google Cloud con facturación para **Vertex AI** | 41 | Sí: es la condición para usar datos de salud sin que entrenen modelos |
| D2 | Segundo proveedor de IA y su clave | 41 | Claude (Anthropic) o OpenAI; local con Ollama solo para desarrollo |
| D3 | Dónde guardar los respaldos fuera del equipo | 42 | Un bucket con capa gratuita (Backblaze B2 o Cloudflare R2) con rclone |
| D4 | Correo que recibe las alertas | 43 | El tuyo |
| D5 | Producto principal de la beta: **personas** u organizaciones | 45 | Personas: todo lo de los Planes B y C apunta ahí |

Fuera del código y en paralelo: revisión del abogado (`docs/revision-legal.md`), revisión médica (`docs/revision-medica/`), revisión del glosario, dominio y VPS.

## Sprint 40: Cuentas seguras

Hoy no se puede recuperar una contraseña olvidada, ni cambiarla, ni cerrar sesión de verdad.

- **Sesiones revocables (V14):** tabla `sesiones` con el identificador de cada token de renovación (solo su hash). Al renovar se rota (el anterior deja de servir); si se reutiliza uno ya rotado, se cierran todas las sesiones de la cuenta (señal de robo).
- **Cerrar sesión** (`POST /auth/logout`) y **cerrar todas mis sesiones**, desde el menú del usuario.
- **Olvidé mi contraseña:** enlace de un solo uso por correo (30 minutos, solo el hash en la base, mismo patrón que la verificación de correo), respuesta idéntica exista o no la cuenta, con límite por IP y por correo. Al restablecerla se cierran todas las sesiones.
- **Cambiar contraseña** con la actual; también cierra las demás sesiones y avisa por correo.
- **Contraseñas comprometidas:** se rechazan las que aparecen en filtraciones (k-anonimato contra Have I Been Pwned: solo viajan 5 caracteres del hash) y las más comunes.
- **Verificación en dos pasos (TOTP)** opcional para todos y obligatoria para administradores de organizaciones, con códigos de respaldo.
- Pruebas: rotación y reutilización de tokens, enlaces vencidos y usados, enumeración de cuentas, TOTP con reloj desfasado.

## Sprint 41: IA de producción

Hoy todo va a la API gratuita de Gemini (que puede usar lo que recibe) y a un solo proveedor.

- **Proveedor Vertex AI** (Gemini en Google Cloud) detrás de `ProveedorLLM` y `ProveedorEmbeddings`: cuenta de servicio, región elegible, sin entrenamiento con los datos. Mismos modelos de embeddings, así que no hace falta reindexar.
- **Segundo proveedor** (D2) con la misma interfaz y **respaldo automático**: si el principal falla o se satura, responde el segundo; un cortacircuitos evita insistir sobre un proveedor caído.
- Las garantías deterministas (citas, cifras, posología, límites clínicos) se aplican igual a cualquier proveedor; se corre el corpus adverso con cada uno.
- **Costo visible:** tokens y costo estimado por llamada en las métricas, y un tope diario configurable.
- Configuración por entorno: en producción, la API gratuita queda prohibida (el agente no arranca con ella si `ENTORNO=produccion`).
- Política de privacidad y consentimiento v4 con el proveedor real.

## Sprint 42: Derechos sobre los datos y respaldos que sobreviven

- **Descargar mis datos:** un ZIP con lo que hay de la persona (cuenta, expedientes, texto de sus documentos con su página, consultas, explicaciones, línea de tiempo, recordatorios y consentimientos) en JSON y en una versión legible. Se genera bajo demanda y no se guarda.
- **Retención configurable** de consultas e historial (por ejemplo, borrar automáticamente lo de más de N meses si la persona lo elige).
- **Cifrado en reposo:** disco cifrado documentado como requisito (BitLocker en el PC, LUKS en el VPS) y cifrado de columna para el texto de los fragmentos y las respuestas, con la clave fuera de la base.
- **Respaldos fuera del equipo** (D3): copia cifrada a un bucket con rclone después de cada respaldo, con su propia retención.
- **Restauración de prueba** automática cada mes en un contenedor aparte, con verificación de conteos y de RLS; si falla, alerta.

## Sprint 43: Operación, monitoreo y CI completa

- **Monitoreo:** Prometheus recoge las métricas que ya existen (API, agente, base, cola) y Grafana las muestra; **alertas por correo** (D4) por errores, latencia, cola atascada, respaldo vencido, certificado y costo de IA.
- **Rastreo de errores** del frontend y del backend (GlitchTip autoalojado, compatible con Sentry), sin enviar datos de salud: se limpian textos, nombres y cuerpos antes de reportar.
- **CI:** Dependabot y CodeQL, construcción y escaneo de las imágenes Docker (Trivy), **pruebas de punta a punta en navegador con Playwright** (registro, subir foto, explicar, línea de tiempo, preparar cita, recordatorio, borrar cuenta) y la misma versión de Java en CI y en el equipo.
- **Versiones:** etiquetas semver, CHANGELOG generado de los commits y `main` como la rama de lo publicado (se pone al día con `develop` cuando el dueño lo decida).
- **Portada liviana:** videos recodificados con ffmpeg (fotogramas clave densos, sin audio, menos peso), imágenes fijas en datos móviles y etiquetas Open Graph, `robots.txt` y `sitemap.xml`.
- Separar html2canvas del PDF y sacarlo del caché del teléfono.

## Sprint 44: Calidad de la IA medida y privacidad más fuerte

- **Conjunto de evaluación** con documentos reales anonimizados (o sintéticos realistas) y respuestas esperadas: qué tan seguido se recupera el fragmento correcto, qué tan seguido la cita respalda lo dicho, qué tan seguido se abstiene cuando debe, y lo mismo para explicar, la línea de tiempo y la preparación. Corre cada noche con el modelo real y falla si una métrica baja.
- **Segunda capa de anonimización** con reconocimiento de entidades en español (spaCy o Presidio) para nombres sin etiqueta, medida contra un corpus propio (cuántos nombres se escapan y cuántas palabras se tapan de más).
- **Línea de tiempo por documento al indexar:** los eventos y valores se extraen una vez por documento y se guardan, así un expediente largo no se corta en 60 fragmentos y abrir la línea no llama al modelo.

## Sprint 45: Producto para familias

- **Cuidadores:** compartir un expediente personal con un familiar por invitación de correo, con permiso de lectura o de edición, revocable, auditado y con aviso a la persona dueña. Respeta los recordatorios de cada quien.
- **Accesibilidad:** tamaño de letra ajustable, **lectura en voz alta** de las explicaciones (voz del sistema, sin enviar el texto a nadie), alto contraste y revisión con lector de pantalla.
- **Notificaciones push** de la app instalada para los recordatorios (claves VAPID), sin datos de salud en el texto, como alternativa al correo.
- Según D5, ordenar la portada y el lenguaje alrededor del producto principal.

## Orden y dependencias

40 y 41 primero (en cualquier orden; 41 necesita D1). 42 después de 40 (el ZIP usa la sesión nueva). 43 en cualquier momento, idealmente antes de abrir la beta a más gente. 44 después de 41 (la evaluación corre con el proveedor de producción). 45 al final.

## Verificación de cada sprint

`pytest` y `ruff` (agente), `mvn test` (API), `npm test`, `tsc` y build (frontend), recorrido real con el proveedor de IA real y revisión de la pantalla en el navegador. Desde el sprint 43, además, Playwright y la CI en verde en GitHub.
