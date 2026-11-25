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

**Hecho (25-nov-2026):**
- V14: `sesiones` (hash del jti, familia, rotación, revocación), `restablecimientos_clave`, `codigos_respaldo` y en `usuarios` la fecha desde la que valen los tokens y el TOTP cifrado. Todo con RLS.
- Los tokens llevan `emitido_ms`: el `iat` en segundos no alcanzaba para invalidar sesiones en el mismo segundo.
- Endpoints: `/auth/logout`, `/auth/cerrar-sesiones`, `/auth/cambiar-contrasena`, `/auth/olvide-contrasena`, `/auth/restablecer-contrasena`, `/auth/2fa` (estado, iniciar, activar, desactivar, verificar). El ingreso devuelve un desafío de 5 minutos cuando la cuenta tiene dos pasos.
- Política de contraseñas en registro, alta por administrador, cambio y restablecimiento: mínimo 10, comunes, con el nombre o el correo, y filtradas (Have I Been Pwned por k-anonimato; si no responde, no bloquea).
- Dos pasos obligatorios para administradores de organizaciones con `DOS_PASOS_ADMINS=true` (activado en el compose de producción). Secretos TOTP cifrados con `CIFRADO_CLAVE`.
- Correos de aviso en cada cambio sensible, ahora enviados en segundo plano (antes la respuesta esperaba ~6 s a Brevo).
- Frontend: segundo paso en el ingreso, «¿Olvidaste tu contraseña?», página de restablecer y «Seguridad de la cuenta» (QR dibujado en el navegador, códigos de respaldo, cambio de contraseña y cerrar las demás sesiones). «Cerrar sesión» ahora también la cierra en el servidor.
- Efecto del despliegue: los tokens emitidos antes de V14 no tienen sesión registrada, así que cada persona vuelve a ingresar una vez.

## Sprint 41: IA de producción

Hoy todo va a la API gratuita de Gemini (que puede usar lo que recibe) y a un solo proveedor.

- **Proveedor Vertex AI** (Gemini en Google Cloud) detrás de `ProveedorLLM` y `ProveedorEmbeddings`: cuenta de servicio, región elegible, sin entrenamiento con los datos. Mismos modelos de embeddings, así que no hace falta reindexar.
- **Segundo proveedor** (D2) con la misma interfaz y **respaldo automático**: si el principal falla o se satura, responde el segundo; un cortacircuitos evita insistir sobre un proveedor caído.
- Las garantías deterministas (citas, cifras, posología, límites clínicos) se aplican igual a cualquier proveedor; se corre el corpus adverso con cada uno.
- **Costo visible:** tokens y costo estimado por llamada en las métricas, y un tope diario configurable.
- Configuración por entorno: en producción, la API gratuita queda prohibida (el agente no arranca con ella si `ENTORNO=produccion`).
- Política de privacidad y consentimiento v4 con el proveedor real.

**Hecho (25-nov-2026):**
- `IA_PROVEEDOR=vertex`: Gemini en Google Cloud para generar y para embeddings, con token OAuth firmado localmente desde la cuenta de servicio (o el servidor de metadatos). `gemini-embedding-001` conserva su nombre: no hay que reindexar.
- Claude (Anthropic, `claude-opus-5-5`, SDK oficial con salida JSON estructurada) como segundo proveedor. Si Gemini falla, se satura o rechaza la credencial, responde Claude; el cortacircuitos deja de insistir sobre el caído durante 2 minutos tras 3 fallos seguidos. Una prueba confirma que la salida del respaldo pasa por las mismas garantías.
- Tokens y costo estimado por llamada en métricas y log (solo cifras), y tope diario `IA_TOPE_DIARIO_USD` que corta las llamadas hasta el otro día. Límite: el contador del día está en memoria y se reinicia con el agente.
- Con `ENTORNO=produccion` el agente no arranca con la API gratuita de AI Studio, ni con Vertex sin proyecto, ni con Claude sin clave. El compose de producción monta la cuenta de servicio como secreto (`VERTEX_CREDENCIALES_ARCHIVO`).
- Consentimiento, página legal, preguntas frecuentes y `docs/revision-legal.md` con Google Cloud y Anthropic como encargados.
- **Corrección posterior (25-nov-2026):** la v4 integrada decía Vertex AI sin mirar el proveedor configurado, así que en la beta (API gratuita) habría sido falsa. Ahora el texto y su versión salen del proveedor que el agente tiene activo (`2026-11-v3`, `-v3-claude`, `-v5`, `-v5-claude`), la v4 queda retirada y ningún texto afirma que haya contratos firmados. No llegó a desplegarse en la beta desde este repositorio.
- **Pendiente del dueño:** D1 (proyecto de Google Cloud con facturación, Vertex AI habilitado y la cuenta de servicio) y D2 (clave de Anthropic) para el recorrido real; aceptar los DPA de los dos.

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
