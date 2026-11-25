import { useQuery } from "@tanstack/react-query";
import { api } from "../api/cliente";

/**
 * Lo que la interfaz dice sobre la IA de terceros sale del proveedor que el servidor tiene activo (la API se
 * lo pregunta al agente, que es quien envía los datos). Todos esos textos viven aquí. Cambiar el del
 * consentimiento exige subir sus versiones en `ConsentimientoService.java`.
 */
export interface ProveedorIa {
  proveedor: "gemini_api" | "vertex";
  respaldo: "" | "claude";
}

/** Si no se conoce con certeza el proveedor, devuelve `null`: no se supone ninguno. */
export function proveedorDe(proveedor?: string, respaldo?: string): ProveedorIa | null {
  if ((proveedor !== "gemini_api" && proveedor !== "vertex") || (respaldo !== "" && respaldo !== "claude")) return null;
  return { proveedor, respaldo };
}

/** Punto del consentimiento que dice quién recibe los documentos y qué puede hacer con ellos. */
export function textoConsentimientoIa({ proveedor, respaldo }: ProveedorIa): string {
  if (proveedor === "gemini_api") {
    const gratis =
      "Para leerlos y responderte usamos un servicio de inteligencia artificial de un tercero: Google Gemini, que puede procesar la información fuera de Colombia. En esta etapa usamos su versión gratuita, y Google puede conservar y usar lo que se le envía para mejorar sus productos. Por eso sube solo lo que necesites.";
    return respaldo
      ? `${gratis} Si Gemini falla, tu pregunta y fragmentos de tus documentos pueden ir a Claude, de Anthropic, otra empresa que no usa lo que le enviamos para entrenar sus modelos.`
      : gratis;
  }
  return respaldo
    ? "Para leerlos y responderte usamos servicios de inteligencia artificial de terceros: Gemini en Google Cloud (Vertex AI) y, solo si ese servicio falla, Claude de Anthropic. Pueden procesar la información fuera de Colombia. Ninguno de los dos usa lo que les enviamos para entrenar sus modelos. Aun así, sube solo lo que necesites."
    : "Para leerlos y responderte usamos un servicio de inteligencia artificial de un tercero: Gemini en Google Cloud (Vertex AI), que puede procesar la información fuera de Colombia. Google no usa lo que le enviamos para entrenar sus modelos. Aun así, sube solo lo que necesites.";
}

/** Resumen para las páginas públicas (privacidad y preguntas frecuentes). */
export function resumenIa(ia: ProveedorIa | null): string {
  if (!ia) {
    return "Para leer los documentos y responder usamos servicios de inteligencia artificial de terceros, que pueden procesar la información fuera de Colombia. Antes de aceptar el consentimiento verás cuáles son y si pueden usar lo que reciben.";
  }
  if (ia.proveedor === "gemini_api") {
    const gratis =
      "Para leer los documentos y responder usamos Google Gemini, un servicio de inteligencia artificial de un tercero que puede procesar la información fuera de Colombia. En esta etapa usamos la versión gratuita de Google, que puede usar lo que recibe para mejorar sus productos.";
    return ia.respaldo
      ? `${gratis} Si Gemini falla, respondemos con Claude, de Anthropic, que no usa lo que recibe para entrenar sus modelos.`
      : gratis;
  }
  const vertex =
    "Para leer los documentos y responder usamos Gemini en Google Cloud (Vertex AI), un servicio de inteligencia artificial de un tercero que puede procesar la información fuera de Colombia y que no usa lo que recibe para entrenar sus modelos.";
  return ia.respaldo
    ? `${vertex} Solo si ese servicio falla usamos Claude, de Anthropic, que tampoco usa lo que recibe para entrenar sus modelos.`
    : vertex;
}

/** Proveedor activo para las páginas sin sesión. Mientras no se sepa, `null`. */
export function useProveedorIa(): ProveedorIa | null {
  const { data } = useQuery({
    queryKey: ["proveedor-ia"],
    queryFn: () => api<{ proveedor: string; respaldo: string }>("/publico/ia"),
    staleTime: 60_000,
    retry: false,
  });
  return proveedorDe(data?.proveedor, data?.respaldo);
}
