/**
 * Lo único que dice una notificación. El servidor la envía SIN contenido: este texto fijo lo pone la
 * aplicación en el teléfono, así que en la pantalla bloqueada nunca aparece nada de salud.
 */
export const AVISO_PUSH = {
  titulo: "MedTender",
  cuerpo: "Tienes un recordatorio. Ábrelo en la aplicación.",
  etiqueta: "medtender-recordatorio",
  destino: "/recordatorios",
} as const;
