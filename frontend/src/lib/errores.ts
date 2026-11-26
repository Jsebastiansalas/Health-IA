import type { ErrorEvent } from "@sentry/browser";

/**
 * Rastreo de errores de la web (GlitchTip o compatible con Sentry), sin datos de salud. El SDK no recoge nada por
 * su cuenta (solo los errores no capturados) y cada evento **se construye de nuevo con lo permitido**: tipo del
 * error y archivo, función y línea. Ni mensajes, ni direcciones de página, ni navegador, ni usuario, ni migas.
 * Sin `VITE_ERRORES_DSN` está apagado y el SDK ni se descarga.
 */
export function limpiar(evento: ErrorEvent): ErrorEvent | null {
  const excepciones = evento.exception?.values;
  if (!excepciones?.length) return null;
  const soloRuta = (archivo?: string) => archivo?.replace(/^[a-z]+:\/\/[^/]+/i, "").split(/[?#]/)[0];
  return {
    type: undefined,
    event_id: evento.event_id,
    timestamp: evento.timestamp,
    platform: evento.platform,
    level: evento.level,
    environment: evento.environment,
    release: evento.release,
    tags: { servicio: "web" },
    exception: {
      values: excepciones.map((e) => ({
        type: e.type,
        value: "",
        stacktrace: {
          frames: (e.stacktrace?.frames ?? []).map((m) => ({
            filename: soloRuta(m.filename),
            function: m.function,
            lineno: m.lineno,
            colno: m.colno,
            in_app: m.in_app,
          })),
        },
      })),
    },
  };
}

export async function activarRastreo(dsn: string | undefined): Promise<boolean> {
  if (!dsn) return false;
  const Sentry = await import("@sentry/browser");
  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
    defaultIntegrations: false,
    integrations: [Sentry.globalHandlersIntegration()],
    maxBreadcrumbs: 0,
    sendClientReports: false,
    beforeSend: limpiar,
  });
  return true;
}
