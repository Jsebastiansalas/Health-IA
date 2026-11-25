# Plan C: MedTender como aplicación y un agente que hace más (sprints 36–39)

Decidido el 25-nov-2026: **app web instalable (PWA)**, y tres funciones nuevas del agente: **línea de tiempo y evolución de resultados**, **preparar mi cita** y **recordatorios de controles**. Rige el mismo flujo: un sprint por rama `feature/*`, resumen al final, «Integrar y seguir».

Reglas que no cambian en ninguna función nueva:
- Todo dato que se muestre sale de un documento del usuario y lleva su cita (documento, página, texto exacto). Si no hay cita, no se muestra.
- No se diagnostica, no se receta, no se dosifica y no se dice si un valor es bueno o malo: se muestra el valor y el rango **tal como vienen impresos**.
- El texto va anonimizado a Gemini, los límites clínicos (`seguridad.detectar_limite_clinico`) y las garantías de salida (`garantias`) se aplican igual que en Explicar y Cruce.
- Cada endpoint nuevo exige consentimiento y correo verificado, respeta RLS y deja auditoría solo con ids y conteos.

## Sprint 36: MedTender como app (PWA)

Primero, porque todo lo demás se usará sobre todo desde el celular.

- **Instalable:** `manifest.webmanifest` (nombre, colores `#0b2e4a`/`#f4f7fa`, iconos 192/512 y *maskable* derivados de la marca), `display: standalone`, `start_url: /expedientes`.
- **Service worker** (`vite-plugin-pwa`, Workbox): guarda en caché solo el armazón de la app (HTML, JS, CSS, fuentes, iconos). **Nunca** guarda respuestas de `/api`, documentos ni videos de la portada: los datos de salud no quedan en el teléfono. Pantalla «Sin conexión» propia.
- **Cámara directa:** en «Cargar documento», botón «Tomar foto» (`capture="environment"`) además de elegir archivo.
- **Recibir desde «Compartir»:** `share_target` en el manifiesto (POST multipart). El service worker recibe la foto o el PDF, lo guarda un momento en IndexedDB y abre la app en «¿A qué expediente lo subo?»; al subirlo o cancelarlo se borra. Android y escritorio; en iPhone no existe y se dice en la ayuda.
- **Actualizaciones:** aviso «Hay una versión nueva» con botón para recargar.
- Caddy: cabeceras correctas para `sw.js` y el manifiesto (sin caché larga).
- Pruebas: vitest del flujo de compartir (IndexedDB simulada); Lighthouse PWA en el navegador; instalación real en Android por el dueño.

## Sprint 37: Línea de tiempo y evolución de resultados

- **Agente** (`agente/app/rag/cronologia.py`, `POST /internal/v1/cronologias`): recorre los documentos del expediente y extrae, con salida JSON con esquema:
  - **Eventos:** fecha, tipo (consulta, examen, hospitalización, procedimiento, fórmula, control indicado) y una frase literal con su cita.
  - **Valores de laboratorio:** analito normalizado (tabla de sinónimos en `glosario_datos`: «Hb», «Hemoglobina»…), valor, unidad, rango impreso, marca impresa (ALTO/BAJO si el documento la trae), fecha y cita.
  - Validación determinista: el número, la unidad y la fecha deben aparecer en el extracto citado (`localizar_extracto`); si no, se descarta. Fechas ambiguas se muestran como el documento las escribe.
- **Persistencia:** tabla `evento_clinico` (V13) con FORCE RLS por tenant, para no recalcular: se regenera cuando entra o se borra un documento.
- **Java:** `GET /api/v1/expedientes/{id}/cronologia` (LECTOR), patrón de `CruceController`.
- **Frontend:** pestaña «Línea de tiempo» en el expediente: lista por fecha con filtros por tipo, y por cada analito una gráfica simple de su evolución con el rango impreso como banda; cada punto abre su cita. Sin colores de «bueno/malo»: solo la marca que trae el documento.
- Pruebas: documentos sintéticos con el mismo analito en tres fechas, sinónimos, una fecha ambigua y un valor que el modelo inventa (debe descartarse).

## Sprint 38: Preparar mi cita

- **Agente** (`POST /internal/v1/preparaciones`): a partir de la cronología (sprint 37), el cruce y Explicar, arma un resumen de una página:
  - documentos recientes y lo que dicen (con cita),
  - medicamentos que aparecen en los documentos (sin dosis inventadas, solo el texto citado),
  - valores que cambiaron entre fechas (solo los datos, sin interpretar),
  - preguntas sugeridas para el médico, y un espacio para las del usuario.
- **Java:** `POST /api/v1/expedientes/{id}/preparacion` y descarga en **PDF** generado en el servidor (OpenPDF), con el aviso «no es un diagnóstico» y la fecha de generación. El PDF no se guarda: se genera y se entrega.
- **Frontend:** botón «Preparar mi cita» en el expediente, vista previa editable de las preguntas, «Descargar PDF» y «Compartir» (Web Share en el celular).
- Pruebas: que ninguna línea del PDF quede sin cita, que una petición de dosis dentro de las preguntas dispare el límite clínico.

## Sprint 39: Recordatorios de controles

- **Agente:** de la cronología toma los eventos tipo «control indicado» y las citas con fecha («control en 3 meses», «cita el 12/02»), y calcula la fecha propuesta a partir de la fecha del documento. Cada recordatorio lleva su cita.
- **Persistencia:** tabla `recordatorio` (V14) con RLS: fecha, texto citado, estado (propuesto, confirmado, hecho, descartado). **El usuario confirma** cada recordatorio antes de que se active; nada se programa solo.
- **Avisos:** correo con Brevo (ya configurado) unos días antes, con un texto neutro que no repite datos de salud en el asunto; descarga de evento de calendario `.ics`. Notificaciones push de la PWA como mejora opcional al final del sprint (requiere claves VAPID).
- No se crean recordatorios de tomas de medicamentos (sería dosificar).
- Pruebas: cálculo de fechas relativas, recordatorio sin fecha clara (queda propuesto con el texto, sin fecha), envío de correo con el doble de prueba.

## Orden y dependencias

36 (PWA) es independiente. 37 → 38 y 39 (las dos usan la cronología). Si se prefiere ver valor del agente antes, 37 puede ir primero.

## Fuera de alcance

Interpretar imágenes médicas, recomendar tratamientos, recordatorios de tomas, publicar en Play Store o App Store (queda para cuando haya cuentas de desarrollador), compartir el expediente con otra persona (candidato para un Plan D).

## Verificación por sprint

`uv run python -m pytest` y `ruff` (agente), `mvn test` (API), `npm test` y `tsc` (frontend), recorrido real en el navegador y, en el 36, instalación en un teléfono Android.
