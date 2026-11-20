---
name: MedTender
description: El expediente físico: una carpeta de cartulina manila con folios de papel; cada cita se marca a mano con resaltador.
colors:
  mesa-papel: "#e6e5df"
  folio-papel: "#fcfcfa"
  folio-2-papel: "#efeee8"
  carpeta-papel: "#dcc185"
  carpeta-osc-papel: "#c9a95e"
  tinta-papel: "#151c33"
  tinta-2-papel: "#404863"
  tinta-3-papel: "#596079"
  accion-papel: "#2336a6"
  marca: "#ffe566"
  ok-papel: "#1d6b47"
  aviso-papel: "#8a4f00"
  peligro-papel: "#b3261e"
  mesa-nocturno: "#0f121a"
  folio-nocturno: "#181d2a"
  folio-2-nocturno: "#222a3c"
  carpeta-nocturno: "#3a3225"
  tinta-nocturno: "#ebe8dd"
  accion-nocturno: "#93a5ff"
typography:
  display:
    fontFamily: "Source Serif 4 Variable, Georgia, serif"
    fontSize: "clamp(2.4rem, 5vw, 4.2rem)"
    fontWeight: 600
    lineHeight: 1.08
    letterSpacing: "-0.012em"
  headline:
    fontFamily: "Source Serif 4 Variable, Georgia, serif"
    fontSize: "1.9rem"
    fontWeight: 600
    lineHeight: 1.18
  body:
    fontFamily: "Atkinson Hyperlegible Next Variable, Segoe UI, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Geist Mono Variable, Consolas, monospace"
    fontSize: "0.72rem"
    letterSpacing: "0.02em"
rounded:
  folio: "4px"
  control: "6px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "40px"
components:
  boton-primario:
    backgroundColor: "{colors.accion-papel}"
    textColor: "#ffffff"
    rounded: "{rounded.control}"
    height: "40px"
    padding: "0 20px"
  boton-secundario:
    backgroundColor: "{colors.folio-papel}"
    textColor: "{colors.tinta-papel}"
    rounded: "{rounded.control}"
    height: "40px"
  campo:
    backgroundColor: "{colors.folio-papel}"
    textColor: "{colors.tinta-papel}"
    rounded: "{rounded.control}"
    height: "44px"
    padding: "0 12px"
  insignia-sello:
    textColor: "{colors.tinta-2-papel}"
    rounded: "3px"
    padding: "2px 8px"
  folio:
    backgroundColor: "{colors.folio-papel}"
    textColor: "{colors.tinta-papel}"
    rounded: "{rounded.folio}"
  nav-activo:
    backgroundColor: "{colors.folio-papel}"
    textColor: "{colors.tinta-papel}"
    rounded: "{rounded.control}"
---

# Design System: MedTender

## Overview

**Creative North Star: "El Expediente"**

En Colombia un expediente es una carpeta de cartulina manila con folios foliados dentro. MedTender conserva ese objeto: la **carpeta** (manila) es la estructura que sostiene la navegación; el **folio** (papel) es donde se lee y se trabaja; la **tinta** es azul-negra; y lo que importa, la cita, se marca con **resaltador** sobre el texto original. Nada decora: cada material tiene una función.

Hay dos temas del mismo objeto. **Papel** (día, por defecto): mesa gris cálida, folios casi blancos, carpeta manila. **Nocturno** (luz baja): mesa azul noche, folios de grafito azulado, carpeta de manila a media luz, tinta marfil. El orden de las superficies es idéntico; solo cambia la luz. El tema sigue el del sistema operativo y el usuario puede fijarlo desde el menú de su cuenta.

Rechaza lo confirmado: el degradado de montañas con luna, los fondos de gris-violeta con un acento cobalto copiados de un producto financiero, las pastillas en todo, y los nombres de token heredados de mundos descartados (microscopio, negatoscopio).

**Key Characteristics:**
- Cuatro materiales con rol fijo: mesa, carpeta, folio, resaltador. Una sola acción de color: tinta azul.
- Serif de documento legal para los titulares; sans de alta legibilidad para la interfaz; monoespaciada solo para huellas, códigos y cifras.
- Esquinas casi rectas (folio 4 px, controles 6 px); sin pastillas.
- La cita es la pieza protagonista: texto original con resaltador, página y huella.

## Colors

Estrategia: neutros cálidos (mesa y folios), un bloque comprometido de color (la carpeta manila en la barra lateral) y dos acentos con roles excluyentes. Cada token tiene un valor por tema en `index.css`; los componentes usan solo los nombres semánticos.

### Primary
- **Tinta azul** (`accion`): la acción principal, enlaces, foco y estado activo. `#2336a6` en papel, `#93a5ff` en nocturno. El texto encima es `accion-tx` (blanco / azul noche).

### Secondary
- **Resaltador** (`marca`): `#ffe566` en ambos temas, siempre con `marca-tx` encima. Solo para lo citado: referencias [n] de la respuesta, texto de la cita en el visor, la selección de texto. Nunca para estado activo ni para decorar.

### Neutral
- **Mesa** (`mesa`): fondo de la aplicación. **Folio** (`folio`): tarjetas, menús, diálogos, campos. **Folio 2** (`folio-2`): controles secundarios, pozos y hover.
- **Carpeta** (`carpeta`, `carpeta-osc`): cartulina manila de la barra lateral y la barra superior; el elemento activo es un folio que sobresale de ella.
- **Tinta** (`tinta`, `tinta-2`, `tinta-3`): texto principal, secundario y terciario. Bordes y velos son `tinta` con opacidad (`tinta/15` a `tinta/35`), nunca gris neutro.
- Semánticos: `ok` (verificado, huella coincide), `aviso` (advertencia), `peligro` (error o acción destructiva).

### Named Rules
**La Regla de los Dos Acentos.** La tinta azul es lo que se puede hacer; el resaltador es lo que se citó. No se intercambian.
**La Regla de la Carpeta.** La manila es estructura (barra lateral, pestañas), nunca relleno de contenido.
**Contraste verificado.** Todos los pares texto/fondo de ambos temas cumplen AA (mínimo 4,86:1; el texto principal supera 13:1).

## Typography

**Display Font:** Source Serif 4 Variable (tamaño óptico automático), con Georgia.
**Body Font:** Atkinson Hyperlegible Next Variable, con Segoe UI.
**Label/Mono Font:** Geist Mono Variable, con Consolas.

**Character:** titulares con la gravedad de un acta; cuerpo diseñado para distinguir caracteres parecidos, útil en cifras y códigos de licitación; monoespaciada solo donde hay datos exactos.

### Hierarchy
- **Display** (600, `clamp(2.4rem, 5vw, 4.2rem)`, 1.08, -0.012em): titular de la portada.
- **Headline** (600, 1.9rem, 1.18): titulares de página y de sección.
- **Body** (400, 0.95rem, 1.55): texto corrido, `text-wrap: pretty`; medida máxima 65-75ch.
- **Label** (mono, 0.72rem, 0.02em, clase `etiqueta`): huellas SHA-256, códigos de expediente, fechas y números de página, con `tabular-nums` (`.num`).

### Named Rules
**La Regla del Dato en Mono.** Solo datos exactos (huellas, códigos, cifras) van en monoespaciada; nunca como disfraz de "técnico".

## Elevation & Depth

Un folio apoyado en la mesa proyecta una sombra real: desplazada y difusa. Todo lo demás es plano y se separa por contraste de valor.

### Shadow Vocabulary
- **Folio** (`--sombra-folio`; papel: `0 1px 1px rgb(21 28 51 / 0.1), 0 10px 22px -12px rgb(21 28 51 / 0.32)`; nocturno: `0 1px 1px rgb(0 0 0 / 0.35), 0 12px 24px -12px rgb(0 0 0 / 0.7)`): tarjetas, menús, el elemento activo de la barra lateral.

### Named Rules
**La Regla del Folio.** Solo lo que está "sobre la mesa" lleva sombra; los controles no.
**Sin halos.** Nunca sombra de color ni brillo; el foco se dibuja con anillo y halo de `accion` al 22%.

## Shapes

Folio 4 px (papel, casi recto); controles 6 px; sellos de estado 3 px. Un círculo solo para puntos de estado y pasos del proceso. Sin pastillas.

## Components

### Buttons
- **Primario:** fondo `accion`, texto `accion-tx`, 6 px, 40/32/48 px de alto, peso 500, `active:translate-y-px`.
- **Secundario:** fondo `folio`, borde `tinta/35`; hover borde `tinta/60` y fondo `folio-2`.
- **Fantasma:** texto `tinta-2`, hover velo `tinta/7`. **Peligro:** borde y texto `peligro`, hover velo.

### Inputs / Fields
- Alto 44 px, fondo `folio`, borde `tinta/35`, 6 px; etiqueta visible arriba (0.85rem, `tinta-2`). Foco: borde `accion` y halo de 3 px.

### Insignias (sellos)
- Rectangulares de 3 px, borde fino del color y fondo al 10 %; `marca` es el único relleno sólido (texto citado).

### Navigation
- Barra lateral manila (`carpeta`); el ítem activo es un folio (`folio` + sombra) que sobresale; inactivos con hover `tinta/8`. En móvil, barra superior manila. Menú de usuario: folio, con cambio de tema y cierre de sesión.

### Logotipo
- Un folio con la esquina doblada, una «M» a tinta y el resaltador pasado por debajo, como queda una cita marcada. El folio y la tinta toman el color del texto; el resaltador es siempre amarillo. Favicon en `public/favicon.svg`.

## Do's and Don'ts

### Do:
- **Do** usar los nombres semánticos (`mesa`, `folio`, `carpeta`, `tinta`, `accion`, `marca`) y nunca valores hexadecimales en componentes.
- **Do** resaltar lo citado con `.resaltado` o `bg-marca text-marca-tx`.
- **Do** verificar cada par nuevo de colores contra AA en los dos temas.
- **Do** mantener el movimiento con `--ease-salida` y respetar `prefers-reduced-motion`.

### Don't:
- **Don't** usar pastillas (`rounded-full`) en controles, chips o buscadores.
- **Don't** usar el resaltador como estado activo ni la tinta azul para marcar citas.
- **Don't** añadir sombras a los controles ni halos de color.
- **Don't** volver al fondo de montañas, al gris-violeta con cobalto ni a la rejilla de tarjetas con icono como estructura de página.
- **Don't** introducir fuentes desde un CDN: la CSP exige que estén empaquetadas.

<!-- Pantallas aún sin rediseñar a este sistema (sprints 19 a 22): detalle de expediente, listado, citas, Medicamentos, portada e ingreso. Usan los tokens nuevos pero conservan su estructura anterior. -->
