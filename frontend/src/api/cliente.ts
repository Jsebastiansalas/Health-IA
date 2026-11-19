import type { Documento, Tokens } from "./tipos";

const BASE = "/api/v1";
const CLAVE = "medtender.sesion";

// sessionStorage: la sesión termina al cerrar la pestaña. Nunca se guarda en localStorage.
let tokens: Tokens | null = (() => {
  try {
    return JSON.parse(sessionStorage.getItem(CLAVE) ?? "null");
  } catch {
    return null;
  }
})();

export const EVENTO_SESION_EXPIRADA = "medtender:sesion-expirada";

export function haySesion(): boolean {
  return tokens !== null;
}

export function guardarTokens(t: Tokens | null): void {
  tokens = t;
  if (t) sessionStorage.setItem(CLAVE, JSON.stringify(t));
  else sessionStorage.removeItem(CLAVE);
}

export class ErrorApi extends Error {
  constructor(
    public status: number,
    public detalle: unknown,
  ) {
    super(mensajeDe(detalle) ?? `Error ${status}`);
  }
}

function mensajeDe(detalle: unknown): string | undefined {
  if (typeof detalle === "string") return detalle;
  if (Array.isArray(detalle)) return detalle.map((d) => d?.msg ?? String(d)).join(" · ");
  if (detalle && typeof detalle === "object" && "msg" in detalle) return String(detalle.msg);
  return undefined;
}

let refrescando: Promise<boolean> | null = null;

async function refrescar(): Promise<boolean> {
  if (!tokens) return false;
  refrescando ??= (async () => {
    const r = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: tokens?.refresh_token }),
    });
    if (!r.ok) return false;
    guardarTokens(await r.json());
    return true;
  })().finally(() => {
    refrescando = null;
  });
  return refrescando;
}

function expirar(): never {
  guardarTokens(null);
  window.dispatchEvent(new Event(EVENTO_SESION_EXPIRADA));
  throw new ErrorApi(401, "La sesión expiró; vuelva a ingresar.");
}

export async function api<T>(ruta: string, opciones: RequestInit = {}, reintento = true): Promise<T> {
  const headers = new Headers(opciones.headers);
  if (opciones.body && !(opciones.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (tokens) headers.set("Authorization", `Bearer ${tokens.access_token}`);

  const r = await fetch(`${BASE}${ruta}`, { ...opciones, headers });
  if (r.status === 401 && tokens && reintento) {
    if (await refrescar()) return api<T>(ruta, opciones, false);
    expirar();
  }
  if (r.status === 204) return undefined as T;
  const cuerpo = r.headers.get("content-type")?.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new ErrorApi(r.status, (cuerpo as { detail?: unknown })?.detail ?? cuerpo);
  return cuerpo as T;
}

export const post = <T>(ruta: string, cuerpo: unknown) =>
  api<T>(ruta, { method: "POST", body: JSON.stringify(cuerpo) });

/** Subida multipart con progreso real de bytes (fetch no lo expone). */
export function subirPdf(
  expedienteId: string,
  formulario: FormData,
  alProgresar: (fraccion: number) => void,
): Promise<Documento> {
  return new Promise((resolver, rechazar) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE}/expedientes/${expedienteId}/documentos`);
    if (tokens) xhr.setRequestHeader("Authorization", `Bearer ${tokens.access_token}`);
    xhr.upload.onprogress = (e) => e.lengthComputable && alProgresar(e.loaded / e.total);
    xhr.onerror = () => rechazar(new ErrorApi(0, "No se pudo conectar con el servidor."));
    xhr.onload = () => {
      let cuerpo: unknown = xhr.responseText;
      try {
        cuerpo = JSON.parse(xhr.responseText);
      } catch {
        /* respuesta no JSON */
      }
      if (xhr.status === 202) return resolver(cuerpo as Documento);
      const c = cuerpo as { detail?: unknown; documento?: Documento };
      // 422 por "no es PDF" trae el documento ya purgado: se muestra igual en la lista.
      if (xhr.status === 422 && c.documento) return resolver(c.documento);
      rechazar(new ErrorApi(xhr.status, c.detail ?? cuerpo));
    };
    xhr.send(formulario);
  });
}
