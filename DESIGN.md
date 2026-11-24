---
name: MedTender
description: Registro clínico: el expediente se lee como una historia clínica en pantalla, con el caso arriba, el registro en pestañas y la cita al lado de cada afirmación.
colors:
  fondo-claro: "#f4f7fa"
  panel-claro: "#ffffff"
  panel-2-claro: "#eef2f6"
  borde-claro: "#d3dce5"
  texto-claro: "#14212e"
  texto-2-claro: "#44566a"
  texto-3-claro: "#5a6c80"
  marino: "#0b2e4a"
  primario-claro: "#0e7c86"
  cita-claro: "#fff0b3"
  ok-claro: "#17734a"
  aviso-claro: "#8f5400"
  peligro-claro: "#b42318"
  fondo-oscuro: "#000000"
  panel-oscuro: "#181818"
  panel-2-oscuro: "#1f1f1f"
  borde-oscuro: "#313131"
  primario-oscuro: "#46c2cd"
typography:
  family:
    fontFamily: "Geist Variable, Segoe UI, sans-serif"
    note: "Una sola familia en toda la interfaz; sin cursivas ni pesos por encima de semibold."
  mono:
    fontFamily: "Geist Mono Variable, Consolas, monospace"
    note: "Solo códigos, huellas y cifras (clase .etiqueta)."
  scale: "Escala por defecto de Tailwind con estilos con nombre: heading-1 a 6, title-1 a 5, body-1 a 6, caption-1 a 5 (clases en index.css)."
rounded:
  control: "8px (rounded-lg)"
  panel: "12px"
  marca: "6px (rounded-md) para los marcadores de cita"
spacing: "Solo 2, 4, 8, 12, 16, 24, 32, 40, 48, 64, 80 y 96 px (p-0.5 a p-24 de Tailwind sin los intermedios)."
components:
  boton-primario: "fondo primario, texto primario-tx, 8px, alto 40, px 12, semibold"
  boton-secundario: "fondo panel, borde borde, hover panel-2"
  campo: "alto 40, fondo panel, borde borde, 8px; foco con borde primario y halo del 22 %"
  insignia: "6px, borde completo, un color por significado"
  panel: "fondo panel, borde 1px borde, 12px, sin sombra"
  nav: "barra superior sticky de 56 px; el elemento activo lleva una raya de 2px en primario"
---

# Design System: MedTender

## Overview

**Creative North Star: "El registro clínico"**

El expediente es un registro: arriba el caso en un banner (código en mono, título, entidad, estado, permiso y cuatro cifras), debajo las pestañas del registro (Documentos, Consulta) y, en pantallas anchas, documentos a la izquierda y consulta a la derecha. Todo es superficie plana con una costura de 1 px; la sombra queda solo para lo que flota (menús, avisos). La cita, que es lo que el producto promete, se marca con un resaltado suave y un número en cuadro.

Reemplaza por completo el mundo anterior («Expediente / folio»: cartón manila, serif, sellos, tema oscuro por defecto) por decisión del dueño. Es claro por defecto; el tema oscuro existe como opción y usa solo los grises permitidos por las reglas de elayadesign.

**Key Characteristics:**
- Neutros fríos (gris azulado) con una sola acción de color: verde azulado clínico `#0e7c86`. El azul marino `#0b2e4a` es solo identidad (marca, avatar, bloque de seguridad).
- Una familia tipográfica (Geist) y mono para datos exactos.
- Esquinas de 8 px en controles y 12 px en paneles.
- Paneles que colapsan por prioridad: una tabla pasa a tarjetas en lugar de aplastar columnas.

## Colors

Estrategia restringida: neutros más un acento de acción y un resaltado de cita.

- **Fondo / panel / panel-2:** el lienzo (`#f4f7fa`), las superficies (`#ffffff`) y los pozos o hover (`#eef2f6`).
- **Borde:** la costura de 1 px (`#d3dce5`); todas las líneas finas la usan.
- **Texto / texto-2 / texto-3:** tres niveles azul-grisáceos, todos AA sobre fondo y panel.
- **Primario:** la acción, el foco y el estado activo.
- **Cita:** el resaltado suave de lo citado (`#fff0b3`); es el único amarillo de la interfaz.
- **ok / aviso / peligro:** estados semánticos.
- Tema oscuro: negro `#000000`, paneles `#181818`/`#1f1f1f`, borde `#313131`.

### Named Rules
**La Regla de los Dos Acentos.** El verde azulado es lo que se puede hacer; el amarillo es lo que se citó.
**Sin degradados de fondo.** El único degradado es el del texto del titular de la portada (`#000000` a `#666666` en claro, `#ffffff` a `#9b9b9b` en oscuro).

## Typography

**Family:** Geist Variable para todo; Geist Mono Variable para códigos, huellas y cifras.

Estilos con nombre en `index.css` (cada uno sale de un paso de la escala de Tailwind): `heading-1` a `heading-6`, `title-1` a `title-5`, `body-1` a `body-6`, `caption-1` a `caption-5`. Los tamaños sueltos (`text-[0.72rem]`) no se usan.

### Named Rules
**Sin cursivas ni guiones en los textos.** Los códigos (`DOT-2027-003`) son datos y no cuentan.

## Elevation

Plano. Los paneles se separan por contraste y borde; `shadow-lg` solo en menús desplegables y avisos.

## Components

- **Botón:** primario (relleno primario), secundario (borde), fantasma, peligro; animación de 300 ms con la curva `cubic-bezier(0.22, 1, 0.36, 1)` y `active:scale-[0.98]`.
- **Campo:** etiqueta visible arriba, alto 40, foco con borde primario y halo.
- **Insignia:** pequeña, de borde completo; el relleno sólido amarillo es solo para la cita.
- **Barra superior:** sticky de 56 px, translúcida con desenfoque; navegación con icono (en móvil solo el icono) y menú de usuario. Enlace «Saltar al contenido».
- **Banner del caso:** panel con código en mono, título, entidad, insignias de estado y permiso, y una lista de cifras.
- **Tabla de expedientes:** panel con cabecera y filas; en `lg` es una rejilla de cinco columnas y por debajo, tarjetas apiladas.
- **Portada:** barra flotante centrada y translúcida; titular con degradado de texto (máximo 680 px); ejemplo ilustrativo de respuesta con cita; lema que se revela palabra por palabra; cómo funciona en tres pasos; beneficios; preguntas frecuentes; mismo llamado al cierre. Dos portadas con una oferta cada una: `/` (organizaciones) y `/personas`.
- **Iconos:** Phosphor, importados desde `src/iconos.tsx`.

## Motion

Una sola curva (`cubic-bezier(0.22, 1, 0.36, 1)`): 500 ms para posición y 300 ms para color y opacidad. Solo `transform` y `opacity`; las revelaciones de scroll usan `IntersectionObserver` y ocurren una vez. Con `prefers-reduced-motion` todo pasa a un cambio de opacidad o queda en su estado final.

## Do's and Don'ts

### Do:
- **Do** usar los nombres semánticos (`fondo`, `panel`, `borde`, `texto`, `primario`, `cita`) y nunca hexadecimales en componentes.
- **Do** mantener el espaciado dentro de la tabla (2, 4, 8, 12, 16, 24, 32, 40, 48, 64, 80, 96).
- **Do** dar a cada control hover, activo, foco, carga, vacío y error.

### Don't:
- **Don't** volver a la carpeta manila, la serif, los sellos girados ni el oscuro por defecto.
- **Don't** usar bordes de un solo lado en tarjetas, ni degradados de fondo, ni sombras en controles.
- **Don't** inventar cifras o testimonios en la portada: lo ilustrativo se marca como ejemplo.
- **Don't** introducir fuentes ni iconos desde un CDN: la CSP exige que estén empaquetados.
