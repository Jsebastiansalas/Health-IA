import { useCallback, useSyncExternalStore } from "react";

export type Tema = "papel" | "nocturno";

const CLAVE = "medtender-tema";

/** Tema guardado por el usuario; si no hay, el del sistema operativo. */
export function temaInicial(): Tema {
  try {
    const guardado = localStorage.getItem(CLAVE);
    if (guardado === "papel" || guardado === "nocturno") return guardado;
  } catch {
    /* almacenamiento bloqueado: se usa el del sistema */
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "nocturno" : "papel";
}

export function temaActual(): Tema {
  return document.documentElement.getAttribute("data-tema") === "nocturno" ? "nocturno" : "papel";
}

export function aplicarTema(tema: Tema): void {
  document.documentElement.setAttribute("data-tema", tema);
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", tema === "nocturno" ? "#0f121a" : "#e6e5df");
  try {
    localStorage.setItem(CLAVE, tema);
  } catch {
    /* sin almacenamiento: el cambio vale solo para esta visita */
  }
  window.dispatchEvent(new Event("medtender-tema"));
}

function suscribir(aviso: () => void) {
  window.addEventListener("medtender-tema", aviso);
  return () => window.removeEventListener("medtender-tema", aviso);
}

/** Tema activo y función para alternarlo; se mantiene sincronizado entre componentes. */
export function useTema() {
  const tema = useSyncExternalStore(suscribir, temaActual, () => "papel" as Tema);
  const alternar = useCallback(() => aplicarTema(temaActual() === "papel" ? "nocturno" : "papel"), []);
  return { tema, alternar };
}
