/**
 * ¿Conviene ahorrar datos? En datos móviles, con «ahorro de datos» o con una red lenta la portada muestra las
 * imágenes fijas y no descarga los videos. Si el navegador no informa la conexión (Safari, Firefox), se asume buena.
 */
export function conviveConDatosLimitados(nav: Navigator = navigator): boolean {
  const c = (nav as Navigator & { connection?: { saveData?: boolean; type?: string; effectiveType?: string } }).connection;
  if (!c) return false;
  return c.saveData === true || c.type === "cellular" || ["slow-2g", "2g", "3g"].includes(c.effectiveType ?? "");
}
