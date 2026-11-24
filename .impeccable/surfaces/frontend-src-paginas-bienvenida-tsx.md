---
version: 1
slug: "frontend-src-paginas-bienvenida-tsx"
primary_target: "frontend/src/paginas/Bienvenida.tsx"
related_targets: ["frontend/src/paginas/Ingreso.tsx"]
---

# Surface brief: toda la web de MedTender (portada, ingreso, app)

Scope: portada e ingreso (Persuade) y la app completa (Operate). Reemplazo total del mundo anterior (expediente de cartón, serif, sellos, oscuro) por decisión del dueño: «nada se mantiene, cámbialo todo». Claro por defecto (el oscuro queda como opción, nunca por defecto).
Audience/job: auditor, jurista o biomédico de una entidad de salud, y pacientes o familias con cuenta personal; deciden si confiar y luego revisan expedientes con citas verificables. Acción: ingresar, subir, consultar, abrir la fuente.
Chosen direction: REGISTRO CLÍNICO (la sorteada; el dueño no eligió otra en la ronda y se procede con ella). Sin tablero de decisión cerrado: supuesto declarado.
Unresolved: logotipo definitivo; datos reales (todo ejemplo).

## Direction contract

THESIS: el expediente como una historia clínica en pantalla: el caso arriba en un banner, el registro en pestañas, todo en listas precisas. Rechaza la carpeta de cartón, la sidebar decorada y el SaaS de tarjetas con icono.
OWN-WORLD: fondo azul-gris muy claro #F4F7FA, superficies blancas con costura de 1px #D6DEE6, tinta azul marino #14212E, acción verde-azulado clínico #0E7C86, cita marcada con resaltado suave; sans de trabajo Public Sans, mono solo para códigos y huellas; esquinas 6-8px; sin sombras en controles.
STORY: el visitante ve el caso como un registro clínico ordenado, lee una respuesta con su fuente al lado, confía y trabaja.
FIRST VIEWPORT: barra superior blanca con marca, Expedientes · Medicamentos y usuario; debajo el banner del caso (código mono, título, entidad, estado, permiso) sobre pestañas; documentos a la izquierda, consulta al centro, cita visible; la acción primaria arriba a la derecha.
FORM: Registro clínico, posición 4 de la lista propia, seed cdb7f8c5, con colapso por prioridad (tabla a tarjetas) y rejilla de 8px.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
