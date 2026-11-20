---
name: MedTender
description: Un negatoscopio en un cuarto oscuro azul noche; el expediente es una placa y cada cita se marca a mano en ámbar.
colors:
  sala: "#05080e"
  panel: "#0a1322"
  panel-solido: "#0c1829"
  placa: "#1b2430"
  luz: "#e4f3f8"
  luz-2: "#bfd9e2"
  ink: "#dcecf2"
  tx: "#e8f3f7"
  tx-2: "#a8bcc7"
  tx-3: "#8196a3"
  hema: "#7cd4e6"
  hema-osc: "#a9e5f1"
  hema-pro: "#070d19"
  eosina: "#ffc247"
  eosina-osc: "#ffd27a"
  eosina-clara: "#ffe2a3"
  ok: "#5fe0bf"
  ambar: "#f2b84b"
  coral: "#ff8494"
  lila-50: "#0d1828"
  lila-100: "#111f33"
  lila-200: "#19293f"
  lila-300: "#2b4059"
typography:
  display:
    fontFamily: "Archivo Variable, Segoe UI, sans-serif"
    fontSize: "clamp(2.8rem, 6.2vw, 5.6rem)"
    fontWeight: 800
    lineHeight: 0.95
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Archivo Variable, Segoe UI, sans-serif"
    fontSize: "1.9rem"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Archivo Variable, Segoe UI, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "Hanken Grotesk Variable, Segoe UI, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 400
    lineHeight: 1.625
  label:
    fontFamily: "JetBrains Mono Variable, Consolas, monospace"
    fontSize: "0.7rem"
    fontWeight: 600
    letterSpacing: "0.08em"
  cera:
    fontFamily: "Reenie Beanie, Segoe Print, cursive"
    fontSize: "2.1rem"
    lineHeight: 1
rounded:
  placa: "3px"
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "16px"
  pill: "999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "40px"
components:
  boton-primario:
    backgroundColor: "{colors.luz}"
    textColor: "#07101c"
    rounded: "{rounded.xl}"
    height: "48px"
    padding: "0 24px"
  boton-primario-hover:
    backgroundColor: "#ffffff"
  boton-secundario:
    backgroundColor: "transparent"
    textColor: "{colors.tx}"
    rounded: "{rounded.lg}"
    height: "40px"
    padding: "0 16px"
  boton-peligro:
    textColor: "{colors.coral}"
    rounded: "{rounded.lg}"
    height: "40px"
  campo:
    backgroundColor: "{colors.sala}"
    textColor: "{colors.tx}"
    rounded: "{rounded.xl}"
    height: "48px"
    padding: "0 14px"
  insignia:
    textColor: "{colors.tx-2}"
    rounded: "{rounded.md}"
    padding: "2px 10px"
  superficie-vidrio:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.tx}"
    rounded: "{rounded.xl}"
  nav-activo:
    backgroundColor: "{colors.luz}"
    textColor: "#07101c"
    rounded: "{rounded.md}"
---

# Design System: MedTender

## Overview

**Creative North Star: "El Negatoscopio"**

Un cuarto oscuro azul noche donde lo unico que ilumina es el panel de luz fria. El expediente es una placa radiografica puesta sobre ese panel, y lo que importa (una cita, una adenda) se marca a mano con rotulador de cera ambar. La interfaz de la app hereda el mismo cuarto, mas calmado: chapas oscuras, filos de luz, nada de brillo decorativo. Tema oscuro por decision del dueno.

El sistema se apoya en tres materiales: la penumbra (`sala`, `panel`), la luz (`luz`, el unico bloque claro y de alto contraste, usado para el panel, el boton primario y el item activo) y la marca a mano (`eosina`, ambar). El cian de pelicula (`hema`) no decora: solo indica estado activo (foco, hover de borde, icono activo). Todo lo grafico (placa, pinzas, perforaciones, trazo) esta dibujado en codigo SVG, sin rasters.

Rechaza lo confirmado: neon sobre negro con brillos, vidrio translucido con difuminado y el heroe SaaS generico. Esta documentado ademas que la direccion anterior (microscopio e histologia) fue descartada.

**Key Characteristics:**
- Penumbra azul noche con un unico panel de luz frio como fuente de claridad.
- Ambar de rotulador solo para hallazgos, citas y adendas; cian solo para estado activo.
- Cuatro familias tipograficas con roles fijos: Archivo comprimido, Hanken, JetBrains Mono, Reenie Beanie.
- Planos, sin vidrio: superficies opacas con filo de luz superior y sombra baja difusa.
- Mecanismo animado en ciclo de 14 s que se detiene en su fotograma de lectura con movimiento reducido.

## Colors

Estrategia: neutros azulados muy oscuros, un bloque claro (la luz) y dos acentos con roles excluyentes. Los nombres de token son heredados de un mundo anterior y cambiaron de significado: `ink` es tinta clara, `hema` es cian de pelicula, `eosina` es ambar de rotulador de cera, `lila-*` son azules oscuros de superficie.

### Primary
- **Luz de Negatoscopio** (`luz`): el panel iluminado, el boton primario, el item de navegacion activo y el avatar. Siempre lleva texto `#07101c`. Gradiente `.panel-luz` con caida de tubo fluorescente hacia `#b9d3dc`.
- **Rotulador de Cera** (`eosina`): marca a mano. Subrayado del titular, hallazgos circulados, caret de campos, seleccion de texto, insignia de adenda. Variantes `eosina-osc` y `eosina-clara` para texto y relleno suave.

### Secondary
- **Cian de Pelicula** (`hema`): solo estado activo. Anillo de foco (2px, offset 3px), borde de campo enfocado con halo `rgb(124 212 230 / 0.22)`, hover de borde del boton secundario, iconos de lista. `hema-osc` para texto sobre oscuro; `hema-pro` (`#070d19`) es en realidad el fondo mas profundo de la barra lateral.

### Neutral
- **Sala** (`sala`): fondo de pagina y de campos. **Panel** (`panel`) y **Panel solido** (`panel-solido`): superficies de app, menus, dialogos.
- **Placa** (`placa`): pelicula gris azulada de la hoja; las placas SVG usan degradado `#2b3947` a `#121a24`.
- **Ink** (`ink`, tinta clara): base de todos los bordes y velos translucidos (`ink/10` a `ink/25`, hover `ink/[0.06-0.1]`).
- **Texto** `tx` (principal), `tx-2` (secundario), `tx-3` (terciario, placeholders, rotulos).
- **Lila 50-300**: escalon de azules oscuros de superficie y scrollbar (`lila-300`).
- Semanticos: `ok` (verificado, huella SHA-256), `ambar` (advertencia), `coral` (peligro/error).

### Named Rules
**La Regla de los Dos Acentos.** El ambar marca lo que importa del expediente; el cian marca lo activo. Nunca se intercambian ni se mezclan en el mismo rol.
**La Regla de la Tinta Clara.** Bordes y velos son `ink` con opacidad, nunca negro ni gris neutro; sobre fondo oscuro la tinta es clara.
**La Regla de una Sola Luz.** El bloque claro (`luz`) es escaso y siempre lleva texto oscuro `#07101c` o `#0a1322`.

## Typography

**Display Font:** Archivo Variable (con Segoe UI), ancho de fuente 88% en h1-h3 (`font-stretch`), 80% en rotulos de acta.
**Body Font:** Hanken Grotesk Variable (con Segoe UI)
**Label/Mono Font:** JetBrains Mono Variable (con Consolas)
**Hand Font:** Reenie Beanie (con Segoe Print), solo para anotacion de rotulador.

**Character:** titulares compactos y pesados, cuerpo limpio y legible, mono para datos de estudio (huellas, fechas, numeros de cita), y una unica voz manuscrita para la marca a mano.

### Hierarchy
- **Display** (800, `clamp(2.8rem, 6.2vw, 5.6rem)`, 0.95, -0.035em): titular del heroe.
- **Headline** (800, 1.9-3.5rem, 1-1.2): titulares de ingreso y secciones.
- **Title** (600, 1.25rem): titulo de dialogos y bloques.
- **Body** (400, 0.95-1.14rem, 1.625): texto corrido, `text-wrap: pretty`, ancho maximo 33rem en el heroe.
- **Label** (mono 600, 0.7rem, 0.08em, mayusculas, clase `rotulo`): datos dentro de placas y pie de figura del negatoscopio; `etiqueta` (mono 0.72rem, 0.04em) para metadatos en linea.
- **Cera** (Reenie Beanie, 2.1rem, rotado -2 grados): anotacion manuscrita sobre la placa, nunca texto funcional.

### Named Rules
**La Regla del Dato en Mono.** Huellas, fechas, numeros de pagina y de fragmento van en JetBrains Mono con `tabular-nums` (`.num`).
**La Regla de la Mano Escasa.** La fuente manuscrita aparece solo como marca sobre una placa o el acta, una o dos veces por pantalla.

## Layout

Landing en rejilla de dos columnas (`1fr / 0.92fr`) con contenedor `max-w-7xl`, titular a la izquierda y negatoscopio a sangre por el borde derecho (`-mr-12` en escritorio); altura de primer viewport `100svh`. Ingreso en dos mitades (`1.1fr / 1fr`): panel de luz con placa a la izquierda (oculto bajo `lg`), formulario a la derecha. La app: barra lateral fija de 16rem con margen 12px (`lg:pl-72`), barra superior pegajosa en movil, contenido `max-w-[1400px]` con relleno `px-4 / sm:px-8`, `py-7 / lg:py-10`. Ritmo basado en pasos de 4px (gaps de 8, 12, 16, 24, 40). Secciones de la landing aparecen una sola vez al entrar en pantalla (24px de desplazamiento, 750 ms).

## Elevation & Depth

Hibrido plano: la profundidad es tonal (`sala` a `panel` a `panel-solido`) mas un filo de luz interior arriba y una sombra baja difusa.

### Shadow Vocabulary
- **Chapa** (`.vidrio`: `inset 0 1px 0 rgb(220 236 242 / 0.06), 0 18px 30px -22px rgb(0 0 0 / 0.8)`): superficies de app.
- **Chapa solida** (`.vidrio-solido`: `inset 0 1px 0 rgb(220 236 242 / 0.07), 0 26px 50px -24px rgb(0 0 0 / 0.9)`): menus, dialogos, tarjeta de ingreso.
- **Placa sobre el panel** (`0 18px 24px -14px rgb(0 0 0 / 0.7)`): la placa asentada sobre la luz.
- **Boton primario** (`0 10px 18px -10px rgb(0 0 0 / 0.9), inset 0 -2px 0 rgb(91 131 146 / 0.45)`).

### Named Rules
**La Regla de Sombra Baja.** Toda sombra es desplazada hacia abajo, con radio negativo y alta opacidad; nunca halo alrededor ni sombra de color.
**La Regla Sin Vidrio.** Pese al nombre heredado de la clase `.vidrio`, las superficies son opacas: sin `backdrop-filter` ni transparencia de fondo.

## Shapes

Esquinas moderadas y escalonadas por tamano: placa 3px (un papel, casi recto), 6px foco y botones sm, 8px insignias y botones sm/nav, 12px botones md y esqueleto, 16px botones lg y campos, 16-24px menus y dialogos (`rounded-2xl`, `3xl` en dialogo), pastilla solo en scrollbar. Bordes de 1px en `ink` translucido. El lenguaje de formas del mundo: pinzas metalicas, perforaciones de pelicula, trazo de rotulador ondulado (SVG con `feDisplacementMap`), grano de pelicula (`feTurbulence`).

## Components

### Buttons
- **Shape:** 8px (sm/icono), 12px (md), 16px (lg). Peso 600, transicion 200 ms con curva `--ease-salida`, `active:translate-y-px`, deshabilitado a 45% de opacidad.
- **Primario:** fondo `luz`, texto `#07101c`, sombra baja con filo inferior; hover a blanco. Altura 40/48.
- **Secundario (por defecto):** transparente, borde `ink/25`, hover borde `hema/70` y velo `ink/[0.06]`.
- **Fantasma:** texto `tx-2`, hover velo `ink/[0.07]`. **Peligro:** borde `coral/40`, fondo `coral/10`.

### Inputs / Fields
- Altura 48px, fondo `sala`, borde `ink/20`, radio 16px, icono `tx-3` a la izquierda. Etiqueta arriba en `tx-2` 0.8rem.
- **Focus:** borde `hema` y halo de 3px `rgb(124 212 230 / 0.22)`; el icono pasa a `hema`.

### Insignias
- Radio 8px, borde y fondo del color al 30-35% / 10%, texto del color, 0.72rem peso 600. Tonos: neutro, hema, eosina, ok, ambar, coral.

### Navigation
- Barra lateral `hema-pro`, borde `ink/10`, radio 16px; item activo en bloque `luz` con texto oscuro; inactivo `tx-2` con hover `ink/[0.08]`. Menu de usuario en chapa solida. Movil: barra superior sobre `sala`.

### Dialogos
- Chapa solida; lateral entra por la derecha (radio izquierdo 24px) o centrado (`34rem`), overlay `black/60`, entrada 300-350 ms.

### Negatoscopio (componente firma)
- Panel de luz con aspecto 4:5, pinzas arriba, la placa del pliego (SVG), cita en tarjeta oscura con insignia `ok` y huella SHA-256 en mono, y acta de purga que aparece al retirarse la placa. Ciclo de 14 s: placa entra, se traza el hallazgo ambar, aparece la nota, la placa se retira y queda el acta. Con movimiento reducido: fotograma de lectura fijo (placa, hallazgo, nota; sin acta).

## Do's and Don'ts

### Do:
- **Do** usar `luz` solo para el panel, el primario y el item activo, siempre con texto `#07101c`.
- **Do** marcar citas y adendas en `eosina`; reservar `hema` para foco y estado activo.
- **Do** construir bordes y velos con `ink` a baja opacidad.
- **Do** mantener todo movimiento con la curva `--ease-salida` y respetar `prefers-reduced-motion`.
- **Do** dibujar ilustraciones en SVG en codigo y rotular lo ficticio como "ejemplo".

### Don't:
- **Don't** usar vidrio translucido, `backdrop-filter` ni brillos de neon (el mundo es de chapa opaca).
- **Don't** usar ambar para estado activo ni cian para hallazgos.
- **Don't** poner sombras de halo ni de color; solo sombras bajas desplazadas.
- **Don't** usar texto claro sobre `luz` ni texto oscuro sobre `sala`.
- **Don't** usar la fuente manuscrita para informacion funcional.

<!-- No canonizado: ver el reporte de la documentacion. Los usos de `rotulo` como etiqueta suelta sobre bloques de la landing (bajo titulos de paso, "Chrome y Edge", pastilla ambar de seccion) y los iconos lucide de la UI son residuos de la construccion, no reglas del sistema. -->
