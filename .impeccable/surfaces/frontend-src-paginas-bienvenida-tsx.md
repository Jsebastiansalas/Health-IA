---
version: 1
slug: "frontend-src-paginas-bienvenida-tsx"
primary_target: "frontend/src/paginas/Bienvenida.tsx"
related_targets: ["frontend/src/paginas/Ingreso.tsx"]
---

# Surface brief: Bienvenida y ingreso (MedTender)

Scope: página pública de bienvenida + ingreso; mode Persuade (el resto de la app es Operate y hereda el mismo mundo, más calmado).
Audience/job: auditor médico, ingeniero biomédico o abogado que decide si confiar en una herramienta con documentos confidenciales. Acción: Ingresar / Empezar. Prueba: el mecanismo (PDF → células → cita verificable → PDF eliminado), mostrado. Contenido de ejemplo (testimonios) permitido solo marcado como ejemplo.
Chosen direction (reemplaza la anterior «noche de quirófano», rechazada por el dueño por genérica): MICROSCOPIO E HISTOLOGÍA, tema claro. Decisión del dueño, manda sobre cualquier sorteo. Momento memorable: la hoja del pliego se deshace en células de un tejido teñido y la célula citada queda señalada con una anotación de micrografía; la hoja desaparece.
Unresolved: logotipo final; fotos reales (ninguna: arte generado en código).

## Direction contract

THESIS: una preparación histológica vista al microscopio: el expediente es un tejido, cada fragmento una célula y cada cita una célula señalada con su anotación. Rechaza el fondo oscuro con neón, vidrio y constelaciones, y el héroe SaaS genérico.
OWN-WORLD: portaobjetos claro (#FAF6FD), tinción H&E a escala de página: eosina rosa-magenta #D9306F y hematoxilina índigo #4B3FC9 con tinta #1A1446; tejido procedural de células (Voronoi, núcleos, fibras), campo de visión circular con retículo, barras de escala en µm y rótulos de aumento en mono; tarjetas blancas con borde lila.
STORY: ve su pliego volverse tejido consultable y desaparecer; cree por la anotación con huella SHA-256; ingresa.
FIRST VIEWPORT: titular a la izquierda sobre un lavado claro del tejido (acción «Empezar» bajo la frase); a la derecha, un campo de microscopio circular que sangra por el borde, con la hoja del pliego deshaciéndose en células y una anotación señalando la célula citada; barra de escala 50 µm y «×40».
FORM: Persuade de mecanismo animado; mundo fijado por el dueño sobre el tema «microscopio e histología».
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
