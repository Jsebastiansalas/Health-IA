/** Tamaño de letra y contraste, elegidos por la persona y guardados solo en su equipo. */
export type Letra = "normal" | "grande" | "muy-grande";

export interface Preferencias {
  letra: Letra;
  contraste: boolean;
}

const CLAVE = "medtender-accesibilidad";
const LETRAS: Letra[] = ["normal", "grande", "muy-grande"];

function guardadas(): Partial<Record<keyof Preferencias, unknown>> {
  try {
    return JSON.parse(localStorage.getItem(CLAVE) ?? "null") ?? {};
  } catch {
    return {};
  }
}

export function leerPreferencias(): Preferencias {
  const g = guardadas();
  const delSistema = typeof window.matchMedia === "function" && window.matchMedia("(prefers-contrast: more)").matches;
  return {
    letra: LETRAS.includes(g.letra as Letra) ? (g.letra as Letra) : "normal",
    contraste: typeof g.contraste === "boolean" ? g.contraste : g.contraste === undefined && delSistema,
  };
}

export function aplicarPreferencias(p: Preferencias = leerPreferencias()): void {
  const raiz = document.documentElement;
  if (p.letra === "normal") delete raiz.dataset.letra;
  else raiz.dataset.letra = p.letra;
  if (p.contraste) raiz.dataset.contraste = "alto";
  else delete raiz.dataset.contraste;
}

export function guardarPreferencias(p: Preferencias): void {
  try {
    localStorage.setItem(CLAVE, JSON.stringify(p));
  } catch {
    // Sin almacenamiento (modo privado): se aplica solo en esta visita.
  }
  aplicarPreferencias(p);
}
