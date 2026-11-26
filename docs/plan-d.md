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
- **Corrección (25-nov-2026), antes de la prueba real:** los valores por defecto no habrían funcionado en Vertex: `gemini-2.5-flash` tenía retiro el 20-oct-2026, `us-central1` no ofrece `gemini-3.8-flash`, las multirregiones usan otro host y el compose local no entregaba la clave. Ahora: `gemini-3.8-flash` con respaldo `gemini-3.5-flash` en `global`, embeddings en `us-central1`, un 404 pasa al siguiente modelo, precios de lista de ambos y `infra/docker-compose.vertex.yml`. Las pruebas con respuestas simuladas no detectan esto: modelos y regiones se revisan en la documentación antes de cada despliegue.
- **Por confirmar en la prueba real:** que la clave JSON de una cuenta de servicio nueva sirva (Google anunció el 27-ago-2026 una restricción temporal a la «Gemini API» desde cuentas de servicio sin decir si incluye Vertex), la dirección que usa la verificación de modelos al arrancar y que 3.8 Flash acepte la petición tal como se envía.
- **Pendiente del dueño:** D1 (proyecto de Google Cloud con facturación, Vertex AI habilitado y la cuenta de servicio) y D2 (clave de Anthropic) para el recorrido real; aceptar los DPA de los dos.

## Sprint 42: Derechos sobre los datos y respaldos que sobreviven

- **Descargar mis datos:** un ZIP con lo que hay de la persona (cuenta, expedientes, texto de sus documentos con su página, consultas, explicaciones, línea de tiempo, recordatorios y consentimientos) en JSON y en una versión legible. Se genera bajo demanda y no se guarda.
- **Retención configurable** de consultas e historial (por ejemplo, borrar automáticamente lo de más de N meses si la persona lo elige).
- **Cifrado en reposo:** disco cifrado documentado como requisito (BitLocker en el PC, LUKS en el VPS) y cifrado de columna para el texto de los fragmentos y las respuestas, con la clave fuera de la base.
- **Respaldos fuera del equipo** (D3): copia cifrada a un bucket con rclone después de cada respaldo, con su propia retención.
- **Restauración de prueba** automática cada mes en un contenedor aparte, con verificación de conteos y de RLS; si falla, alerta.

**Hecho (25-nov-2026):**
- «Mis datos»: descarga en ZIP (JSON y página legible, con la contraseña) y retención del historial a 3, 6, 12 o 24 meses con aviso de lo que se borra. V15.
- Preguntas y respuestas cifradas en la base con `DATOS_CLAVE`, con comando para cifrar lo anterior.
- Copia fuera del equipo con rclone (solo cifrada) y restauración de prueba mensual con conteos exactos y RLS. Probado de punta a punta con PostgreSQL real y una carpeta como «bucket» (`infra/scripts/probar_respaldos.sh`).
- Corregido: la retención dejaba vivir las copias hasta 15 o 16 días aunque el consentimiento dice 14.
- **No se hizo: cifrar el texto de los fragmentos.** El plan lo pedía, pero `fragmentos.fts_vector` se genera en la base a partir de ese texto y es la mitad de la búsqueda; además un índice de palabras sin cifrar revelaría casi el mismo contenido. Queda cubierto solo por el disco cifrado (requisito). **Decisión del dueño** si quiere otra cosa.
- **Pendiente del dueño:** D3 (bucket y su clave limitada) para la prueba con un destino real; activar el disco cifrado; guardar `DATOS_CLAVE` y `BACKUP_PASSPHRASE` fuera del servidor.
- Alerta: hoy es el estado `unhealthy` y el registro; el correo llega con el sprint 43.

## Sprint 43: Operación, monitoreo y CI completa

- **Monitoreo:** Prometheus recoge las métricas que ya existen (API, agente, base, cola) y Grafana las muestra; **alertas por correo** (D4) por errores, latencia, cola atascada, respaldo vencido, certificado y costo de IA.
- **Rastreo de errores** del frontend y del backend (GlitchTip autoalojado, compatible con Sentry), sin enviar datos de salud: se limpian textos, nombres y cuerpos antes de reportar.
- **CI:** Dependabot y CodeQL, construcción y escaneo de las imágenes Docker (Trivy), **pruebas de punta a punta en navegador con Playwright** (registro, subir foto, explicar, línea de tiempo, preparar cita, recordatorio, borrar cuenta) y la misma versión de Java en CI y en el equipo.
- **Versiones:** etiquetas semver, CHANGELOG generado de los commits y `main` como la rama de lo publicado (se pone al día con `develop` cuando el dueño lo decida).
- **Portada liviana:** videos recodificados con ffmpeg (fotogramas clave densos, sin audio, menos peso), imágenes fijas en datos móviles y etiquetas Open Graph, `robots.txt` y `sitemap.xml`.
- Separar html2canvas del PDF y sacarlo del caché del teléfono.

**Hecho (25-nov-2026):**
- Prometheus, Alertmanager y Grafana con alertas probadas (promtool y de punta a punta hasta un buzón falso) y una prueba que impide vigilar métricas que no existen.
- Rastreo de errores sin datos de salud en agente, API y web, probado sobre los bytes enviados y con un GlitchTip real.
- Playwright con la aplicación aislada: recorrido completo de una persona.
- CI: recorrido, infraestructura, Trivy, CodeQL, Dependabot, Java 26 además de 21, CHANGELOG y pasos de versión.
- Portada de 17 a 5 MB de video e imágenes fijas en datos móviles; app instalada de 2,93 a 2,16 MB; Open Graph, robots y sitemap.
- **Errores graves encontrados y corregidos:** en producción la API y los respaldos no tenían salida a internet (ningún correo habría salido y la copia fuera del equipo habría fallado); en modo continuo, un fallo al cifrar se anotaba como copia correcta tras borrarla; sin un SMTP que respondiera, la API quedaba «unhealthy» y no arrancaban el agente ni la web; las variables `VITE_` no llegaban a la web de Docker.
- **Seguridad de las imágenes (Trivy, 25-nov-2026):** se corrigieron los hallazgos altos y críticos con parche: la API (Tomcat, Netty, Jackson y PostgreSQL), el agente (sistema) y los respaldos (sin `gosu`). **Quedan 3 y el flujo `imagenes.yml` estará en rojo por ellos; no se silenciaron:** 2 críticos de `spring-webmvc` 6.2.19 (CVE-2026-47884 y CVE-2026-47890), que solo tienen arreglo en Spring 7, es decir, migrar a Spring Boot 4 (no se evaluó si nuestro uso es explotable); y 1 alto en el binario de Caddy (CVE-2026-78661), a la espera de una versión de Caddy.
- **Revisión de los 2 de Spring (25-nov-2026):** spring.io califica [CVE-2026-47884](https://spring.io/security/cve-2026-47884) como media y [CVE-2026-47890](https://spring.io/security/cve-2026-47890) como baja («crítica» era la severidad que tomaba Trivy de otras fuentes). La primera requiere `XsltView` con una ruta `/**` que dibuje una vista sin nombre; la segunda, fragmentos de vista enviados por SSE. MedTender no cumple ninguna (revisado el código y las rutas de la aplicación arrancada; no se intentó explotarlas). Excepción en `.trivyignore.yaml`, limitada a esos avisos y a `spring-webmvc` 6.2.19, **hasta el 23-feb-2027**; `CondicionesCveSpringIT` falla si la aplicación empieza a cumplir las condiciones (comprobado añadiéndolas). Verificado con el Trivy de la CI: sin excepción fallan por esos 2; con ella pasa; vencida o con otra versión, vuelven. Se quitan la excepción y la prueba al migrar a Spring Boot 4.
- **Migración a Spring Boot 4 (25-nov-2026):** la API pasa a Spring Boot 4.1.3 (Spring Framework 7.0.11, Spring Security 7.1.3, Hibernate 7.4, Flyway 12.4, Tomcat 11) y a Jackson 3. **Se retiraron la excepción** (`.trivyignore.yaml` y su uso en `imagenes.yml`), `CondicionesCveSpringIT` y los parches fijados de Tomcat, Netty, Jackson, PostgreSQL JDBC y Testcontainers: ahora manda el padre. El análisis de la imagen de la API no muestra altas ni críticas con arreglo. Se probó además actualizar una base creada y usada por la versión anterior: Flyway 12 valida las 15 migraciones sin aplicar nada, los tokens ya emitidos siguen sirviendo y la auditoría guardada se lee igual. Cambios a tener en cuenta: (1) Jackson 3 lanza al leer un valor de tipo inesperado sin indicar un valor por defecto, así que en `api-java` se lee siempre con uno (`asString("")`, `asBoolean(false)`); (2) en las métricas, los 401 que rechaza Spring Security salen con `uri="UNKNOWN"` y cambian de nombre algunas métricas de Redis y de Spring Security que ni las alertas ni el panel usan. **La beta sigue con la imagen anterior** hasta que se integre y se reconstruya.
- **Pendiente del dueño:** D4 (`ALERTAS_CORREO`), probar las alertas con el SMTP real, crear las claves de GlitchTip y comprobar los flujos de CI en GitHub (no se han ejecutado allí). El `ci.yml` de pruebas unitarias lo está preparando la otra herramienta y aún no está en el repositorio.

## Sprint 44: Calidad de la IA medida y privacidad más fuerte

- **Conjunto de evaluación** con documentos reales anonimizados (o sintéticos realistas) y respuestas esperadas: qué tan seguido se recupera el fragmento correcto, qué tan seguido la cita respalda lo dicho, qué tan seguido se abstiene cuando debe, y lo mismo para explicar, la línea de tiempo y la preparación. Corre cada noche con el modelo real y falla si una métrica baja.
- **Segunda capa de anonimización** con reconocimiento de entidades en español (spaCy o Presidio) para nombres sin etiqueta, medida contra un corpus propio (cuántos nombres se escapan y cuántas palabras se tapan de más).
- **Línea de tiempo por documento al indexar:** los eventos y valores se extraen una vez por documento y se guardan, así un expediente largo no se corta en 60 fragmentos y abrir la línea no llama al modelo.

**Hecho (25-nov-2026):**
- **Línea de tiempo por documento (V16):** cada documento se lee una vez; lo que propone el modelo se guarda cifrado y se comprueba contra el texto literal cada vez que se arma la línea. Se lee al indexar en las cuentas personales (el worker se lo pide al agente, para que el tope de gasto siga contando en un solo proceso) y, si eso falla, al abrir la línea. Los expedientes largos ya no se cortan en 60 fragmentos (tope: 600 por documento, con aviso). Si el proveedor falla a medias se muestra lo leído, se avisa y no se reutiliza. Sale en «Descargar mis datos» y se borra con el documento. Los documentos anteriores se leen la primera vez que se abre su línea.
- **Segunda capa de anonimización: con reglas y listas, no con NER.** En desarrollo pasa de 4 a 26 de 26 nombres; en el conjunto de reserva (escrito antes que el código y sin ajustar contra él), de 1 a 12 de 18. Sin palabras tapadas de más en ninguno. Se apaga con `ANONIMIZAR_NOMBRES_SUELTOS=false`. **No se usó spaCy ni Presidio:** sus modelos en español hay que descargarlos y los de spaCy son **GPL 3.0** (12,9 MB el pequeño, 42,3 el mediano, 568 el grande): es decisión del dueño. Los 6 nombres que se escapan (poco comunes y sin parentesco ni firma) son el caso en el que un modelo podría ayudar; falta medirlo.
- **Evaluación de calidad:** `uv run python -m evaluacion.correr` (desde `agente/`, con Docker y la clave del proveedor) mide recuperación, respuesta, cita, cifras respaldadas, abstención, límites clínicos, línea de tiempo, explicación, preparación y anonimización, y falla si algo baja de `agente/evaluacion/base.json`. Flujo nocturno `evaluacion.yml`.
- **Lo que la evaluación encontró y se corrigió:** «¿Tengo diabetes?» y «¿Puedo subir (o suspender) la dosis?» llegaban al modelo sin rechazarse; y en un renglón corrido el nombre se llevaba la palabra siguiente («[PERSONA_1] de ingreso» en vez de «Fecha de ingreso»). El segundo ya pasaba antes de este sprint.
- **Sin corregir, para decidir:** (1) las instrucciones de la consola de preguntas siguen siendo las de **licitaciones** («analista experto en licitaciones…», alertas «para el oferente») también para las personas; (2) «Preparar mi cita» sigue leyendo solo los primeros 60 fragmentos para medicamentos, diagnósticos y alergias; (3) el consentimiento no menciona que ahora se guarda lo leído de cada documento (pregunta 9 de `docs/revision-legal.md`).
- **Límites de la evaluación:** documentos inventados (5) y no documentos reales anonimizados; **no se ha corrido con el proveedor real**, así que los mínimos que dependen del modelo son provisionales. El recorrido completo se probó con un modelo simulado.
- **Verificación:** agente 803 pruebas (5 omitidas), API 166, web 89 con `tsc` y build, y el recorrido en navegador con la aplicación aislada (el worker pidió la lectura al indexar y abrir la línea no llamó al modelo; la IA era simulada). Los flujos de CI de esta rama no han corrido en GitHub.
- **Pendiente del dueño:** autorizar la primera corrida real (unas 20 llamadas al modelo) y fijar los mínimos con `--fijar-base`; crear el secreto `GEMINI_API_KEY` (o las de Vertex) en GitHub, con una clave distinta de la de la beta; actualizar `main`, porque GitHub solo ejecuta ahí las tareas programadas.

## Sprint 45: Producto para familias

- **Cuidadores:** compartir un expediente personal con un familiar por invitación de correo, con permiso de lectura o de edición, revocable, auditado y con aviso a la persona dueña. Respeta los recordatorios de cada quien.
- **Accesibilidad:** tamaño de letra ajustable, **lectura en voz alta** de las explicaciones (voz del sistema, sin enviar el texto a nadie), alto contraste y revisión con lector de pantalla.
- **Notificaciones push** de la app instalada para los recordatorios (claves VAPID), sin datos de salud en el texto, como alternativa al correo.
- Según D5, ordenar la portada y el lenguaje alrededor del producto principal.

**Hecho (25-nov-2026):**
- **Cuidadores (V17):** una persona comparte UN expediente por invitación de correo (un solo uso, 7 días, solo para el correo invitado, máximo 5), para ver o también para subir documentos. Revocable; el cuidador puede salir; la dueña recibe aviso al aceptar y al salir, ve cuándo entró y su actividad queda en la auditoría de ella. El cuidador no puede borrar, renombrar, volver a compartir ni borrar el historial. Cada quien usa su consentimiento y guarda sus recordatorios, que se borran al perder el acceso (llevan una cita del documento). Sin servidor de correo, invitar responde con error en vez de fingir el envío.
- **Cómo se aisló:** lo que no se abre de forma expresa sigue cerrado (solo ver el expediente, listar, ver y subir documentos, las funciones de IA y los recordatorios admiten a un cuidador). Mientras dura su petición, políticas RLS restrictivas limitan la base a ese expediente, y no ve usuarios, consentimientos, sesiones ni auditoría de la dueña. Probado también directo contra la base.
- **Accesibilidad:** tres tamaños de letra (ahora relativos al del navegador), alto contraste (respeta el del sistema), «Escuchar» en las explicaciones de documentos **solo con voces instaladas en el equipo** (sin una voz local en español no aparece) y el foco va al contenido al cambiar de pantalla.
- **Notificaciones push (V18):** sin contenido (el texto neutro lo pone la aplicación), solo a los servicios de push de los navegadores, sin seguir redirecciones, y con el correo como respaldo si no llegan. Apagadas hasta crear las claves VAPID (`infra/scripts/generar_vapid.py`).
- **Personas primero (D5, con la recomendación del plan):** la portada principal es la de personas y la de organizaciones pasa a `/organizaciones`; una cuenta personal crea el expediente solo con un nombre y no ve códigos, entidades ni pliegos.
- **Verificación incompleta:** cada bloque pasó sus pruebas al construirlo, pero falta la pasada final: toda la API y el agente con V17 y V18, la web tras el último ajuste del menú, el recorrido en navegador con el paso de cuidadores y la revisión de las pantallas.
- **Corregido de antes:** cerrar sesión y confirmar el correo **nunca quedaban en la auditoría** (la base rechazaba el evento y solo quedaba una línea en el log).
- **Sin probar:** una notificación real en un teléfono (ni en iPhone, que exige instalar la app), la lectura en voz alta con voces reales y un lector de pantalla (NVDA, VoiceOver, TalkBack). Falta esa revisión con personas.
- **Para decidir:** (1) el consentimiento no menciona compartir con cuidadores: la confirmación se pide al invitar y al aceptar (preguntas 10 y 11 de `docs/revision-legal.md`); (2) las preguntas que haga el cuidador quedan en el expediente de la dueña: ella no las ve en su historial, pero sí salen en su «Descargar mis datos», **sin indicar todavía quién las hizo** (falta marcarlas; en la del cuidador no salen), y se borran con el expediente, con el historial o con la cuenta de cualquiera.

## Orden y dependencias

40 y 41 primero (en cualquier orden; 41 necesita D1). 42 después de 40 (el ZIP usa la sesión nueva). 43 en cualquier momento, idealmente antes de abrir la beta a más gente. 44 después de 41 (la evaluación corre con el proveedor de producción). 45 al final.

## Verificación de cada sprint

`pytest` y `ruff` (agente), `mvn test` (API), `npm test`, `tsc` y build (frontend), recorrido real con el proveedor de IA real y revisión de la pantalla en el navegador. Desde el sprint 43, además, Playwright y la CI en verde en GitHub.
