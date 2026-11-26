# Recorrido «scroll-world» de MedTender: un día dentro del hospital

Plan de producción para el fondo animado de la portada (skill `scroll-world`). **Nada se ha generado todavía**: este archivo reúne lo decidido y los textos exactos que se enviarán a Higgsfield, para no gastar créditos improvisando.

## Decisiones (24-nov-2026)

| Tema | Decisión |
|---|---|
| Escenas | 6, en este orden: entrada y urgencias, sala de espera, consultorio, laboratorio, rayos X, habitación |
| Calidad | 720p, solo escritorio (16:9). En el celular se muestra la imagen fija de la primera escena |
| Uso | Portadas `/` y `/personas`. Dentro de la aplicación, las imágenes fijas como fondos discretos (ingreso, estados vacíos), nunca detrás de tablas o textos de trabajo |
| Cámara | Recorrido a pie (arquitectura A de la skill): una sola toma continua que avanza de un lugar al siguiente, como una persona que camina por el hospital |
| Estilo | Diorama isométrico de arcilla mate, como las referencias, con la paleta de MedTender en lugar del lila |
| Contenido | Sin sangre, heridas ni agujas en primer plano: escenas amables (además los filtros de contenido de los modelos de video rechazan escenas médicas fuertes) |

## Costos cotizados en Higgsfield (créditos, 24-nov-2026)

| Pieza | Kling 3.0 (720p nativo) | Seedance 2.0 a 720p |
|---|---|---|
| 6 tramos de recorrido (10 s Kling / 8 s Seedance) | 6 × 15 = 90 | 6 × 36 = 216 |
| Uniones entre escenas, si hicieran falta (5 s) | 5 × 7,5 = 37,5 | 5 × 22,5 = 112,5 |
| 6 imágenes fijas con Nano Banana Pro (2K) | 6 × 2 = 12 | 6 × 2 = 12 |
| **Total sin repeticiones** | **≈ 140** | **≈ 340** |
| **Total con un 40 % de repeticiones** | **≈ 200** | **≈ 480** |

Saldo actual de la cuenta: 10 créditos (plan gratuito). Hace falta comprar créditos antes de empezar. Recomendación: **Kling 3.0** (la skill lo probó y deja las uniones limpias; a 720p cuesta menos de la mitad) y, si una escena sale con poco movimiento, repetir solo esa con Seedance.

## Preámbulo de estilo (idéntico en las 6 imágenes)

```
Isometric low-poly 3D diorama floating as a small rounded island on a plain solid #F4F7FA background with a soft contact shadow beneath it. Soft matte clay 3D render, rounded toy-model shapes, gentle warm studio lighting, soft long shadows, tilt-shift miniature look. Cohesive color palette of deep navy #0B2E4A, clinical teal #0E7C86, soft white #FFFFFF, pale blue-grey #D3DCE5, warm wood #C8A27A and a touch of soft yellow #FFF0B3. Cute chibi clay figurines with round heads: doctors in white coats, nurses in teal scrubs and caps, friendly patients in pale gowns. Calm, clean, reassuring hospital, no blood, no wounds, no needles in close-up. Highly detailed, centered composition, absolutely no text, no letters, no numbers, no logos, no red crosses.
```

## Las 6 escenas (imágenes fijas, 3:2, 2K)

Cada prompt es el preámbulo de arriba seguido de su línea `Subject:`.

1. **Entrada y urgencias**: `Subject: the front of a small modern hospital with a covered entrance and automatic glass doors, a teal ambulance parked under the canopy, a nurse at a triage desk just inside greeting a family, potted plants and benches along a curved path.`
2. **Sala de espera**: `Subject: a bright waiting room with rows of soft chairs, a reception counter with a nurse at a computer, a child playing with blocks in a small play corner, a water dispenser, plants and large windows.`
3. **Consultorio**: `Subject: a doctor's consulting room with a desk, an examination bed with clean paper sheet, a doctor kindly talking with a seated patient holding a folder of documents, shelves with binders, a hand sink and a window.`
4. **Laboratorio**: `Subject: a clinical laboratory with long white counters, microscopes, racks of colored sample tubes, a centrifuge and a refrigerator, two lab technicians in teal scrubs working calmly.`
5. **Rayos X e imágenes**: `Subject: a radiology room with a large X-ray machine and a scanner bed, a separate control booth behind glass where a technician looks at a monitor showing a grey chest image, a patient lying calmly on the bed.`
6. **Habitación**: `Subject: a calm hospital room with two beds with white sheets and teal blankets, a patient sitting up reading, a nurse adjusting a bedside monitor, a visitor chair with flowers, a window with soft daylight.`

Coherencia: la primera imagen aprobada se pasa como referencia a las otras cinco (Nano Banana Pro acepta hasta 14 referencias), para que sean los mismos muñecos y el mismo material.

## Los 6 tramos de video (recorrido a pie, arquitectura A)

Tramo 1 empieza en la imagen de la escena 1; cada tramo siguiente empieza en el **último fotograma real** del tramo anterior (no en la imagen fija). Sin imagen final. Antes de generar el siguiente, revisar ese último fotograma: debe ser un avance tranquilo hacia la próxima puerta; si no, repetir el tramo.

```
Single continuous cinematic camera move, no cuts. Continue the same slow, steady forward glide, as if walking at eye height through the hospital. The camera moves into [ESCENA] toward [PUNTO FOCAL]. In the final second, settle back into a slow, steady forward glide toward the doorway that leads to [SIGUIENTE ESCENA]. Soft matte clay diorama, tilt-shift miniature, warm light, deep navy, clinical teal and soft white palette. Smooth, graceful, slow motion, subtle parallax. No text, no captions.
```

| Tramo | [ESCENA] | [PUNTO FOCAL] | [SIGUIENTE ESCENA] |
|---|---|---|---|
| 1 | the hospital entrance | the triage desk and the nurse greeting the family | the waiting room |
| 2 | the waiting room | the reception counter | the consulting room |
| 3 | the consulting room | the doctor talking with the patient | the laboratory |
| 4 | the laboratory | the microscopes and the racks of tubes | the radiology room |
| 5 | the radiology room | the control booth monitor | the patient rooms |
| 6 | the hospital room | the patient reading by the window | (fin: la cámara se detiene en la ventana) |

Parámetros Kling 3.0: `mode std`, `sound off`, `aspect_ratio 16:9`, `duration 10` (sin parámetro de resolución: entrega 720p nativo).

## Textos de cada tramo en la portada (sin guiones, frase corta)

| Tramo | Título | Texto |
|---|---|---|
| 1 | Llegas con tus papeles | MedTender lee lo que te entregan en urgencias, en el hospital o en la consulta. |
| 2 | Lo subes desde el celular | Una foto o un PDF. El original se elimina del servidor después de leerlo. |
| 3 | Te explica qué dice | En palabras sencillas, con el texto exacto del documento al lado. |
| 4 | Tus resultados, con su fuente | Cada valor viene con su página y su cita. Si el documento no lo dice, te lo dice. |
| 5 | Informes, no imágenes | De una radiografía lee el informe del radiólogo; la imagen no la interpreta. |
| 6 | Llegas a tu cita preparado | Con las preguntas para tu médico. Las decisiones sobre tu salud las toma él. |

## Pasos cuando haya créditos

1. Generar la imagen 1 (2 créditos), revisarla y aprobarla.
2. Generar las imágenes 2 a 6 con la 1 como referencia (10 créditos).
3. Generar los tramos de video en orden, revisando el último fotograma de cada uno.
4. Codificar el video para el scroll (fotogramas clave densos, unos pocos MB) y montar el motor de la skill en las portadas; en el celular, la imagen fija.
5. Exportar las imágenes fijas en WebP para los fondos de la aplicación.

## Lo que se hizo (24-nov-2026)

Se produjo con **Google Flow (Veo)** en lugar de Higgsfield, y con una arquitectura más simple que la del plan: en vez de un recorrido a pie con *Extender*, cada tramo usa *Fotogramas a video* con la escena *i* como primer fotograma y la escena *i + 1* como último. Así las uniones coinciden exactamente y cada escena es una parada donde aparece su texto.

- 6 imágenes fijas (1376×768) → `frontend/public/recorrido/escena-N.webp` y `escena-N-movil.webp`.
- 5 tramos de 3,9 s en 1280×720 → `frontend/public/recorrido/tramo-N.mp4` (sin recodificar: falta ffmpeg).
- Componente `frontend/src/componentes/RecorridoHospital.tsx`, en `/` y `/personas` debajo del inicio. Animado solo en pantallas ≥ 1024 px con ratón y sin movimiento reducido; si no, las 6 escenas fijas con su texto.
- El material original queda en `docs/scroll-world/crudo/` (ignorado por git).

Pendiente: regenerar los tramos 3 y 4 sin oscurecer el fondo (añadir `Keep the plain light background #F0F3F7 throughout, no lens flare, no bokeh, no darkening.`) y recodificar con ffmpeg (`-g 8`, sin audio) si el scroll da tirones.

## Videos de cada escena («entrada», como en la demo de la skill)

En la referencia cada escena tiene su propio video: la cámara entra al diorama y se acerca a la gente. Aquí cada parada es todavía una imagen quieta. Para no rehacer los tramos, cada video de escena **empieza y termina en la misma imagen** (Flow, *Fotogramas a video*, primer y último fotograma = `escena N`): la cámara entra, se acerca y vuelve a salir al mismo encuadre, así empalma con los tramos que ya existen.

Texto (cambiar los dos corchetes):

```
Single continuous cinematic camera move, no cuts. Start exactly on the first image: the [ESCENA] miniature clay diorama seen from above. The camera slowly glides forward and descends into the scene, sweeping in close toward [PUNTO FOCAL], as if flying inside the tiny world, while the little clay figures move gently and naturally. Then the camera smoothly rises and pulls back out, ending exactly on the same view as the last image. Keep the plain light background #F0F3F7 throughout, no lens flare, no bokeh, no darkening. Soft matte clay style, tilt-shift miniature, warm light. Smooth, graceful, slow motion, subtle parallax. No text, no captions, no new objects.
```

| Archivo | [ESCENA] | [PUNTO FOCAL] |
|---|---|---|
| `parada-1.mp4` | hospital entrance | the nurse at the triage desk greeting the family |
| `parada-2.mp4` | waiting room | the nurse at the reception counter |
| `parada-3.mp4` | doctor's consulting room | the doctor talking with the patient holding a folder |
| `parada-4.mp4` | clinical laboratory | the technician looking into the microscope |
| `parada-5.mp4` | radiology room | the technician at the monitor in the control booth |
| `parada-6.mp4` | hospital room | the patient sitting up in bed reading |

Duración: la más larga que ofrezca Flow (8 s), 16:9, descarga en 720p, guardar en `docs/scroll-world/crudo/`.

## Tramos definitivos (25-nov-2026)

Los tramos `tramo-1.mp4` a `tramo-5.mp4` de la portada son ahora los videos «con entrada» (`parada-1` a `parada-5` en `crudo/`): Flow, *Fotogramas a video*, primer fotograma = escena N, último = escena N + 1, 8 s, 720p. La cámara entra en cada escena, se acerca a la gente y sigue por una puerta hasta la siguiente, como en la demo de la skill. Comprobado: cada uno empieza y termina en su imagen y el fondo se mantiene claro. Los tramos cortos de 4 s quedan solo en `crudo/`.
