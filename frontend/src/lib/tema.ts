import { useCallback, useSyncExternalStore } from "react";

export type Tema = "claro" | "oscuro";

const CLAVE = "medtender-tema";

/** Tema guardado por el usuario; si no hay, el claro. El oscuro es una opción, nunca el valor inicial. */
export function temaInicial(): Tema {
  try {
    const guardado = localStorage.getItem(CLAVE);
    if (guardado === "claro" || guardado === "oscuro") return guardado;
  } catch {
    /* almacenamiento bloqueado: se usa el claro */
  }
  return "claro";
}

export function temaActual(): Tema {
  return document.documentElement.getAttribute("data-tema") === "oscuro" ? "oscuro" : "claro";
}

export function aplicarTema(tema: Tema): void {
  document.documentElement.setAttribute("data-tema", tema);
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", tema === "oscuro" ? "#000000" : "#f4f7fa");
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
  const tema = useSyncExternalStore(suscribir, temaActual, () => "claro" as Tema);
  const alternar = useCallback(() => aplicarTema(temaActual() === "claro" ? "oscuro" : "claro"), []);
  return { tema, alternar };
}
