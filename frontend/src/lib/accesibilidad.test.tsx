import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BotonLeer } from "../componentes/BotonLeer";
import { aplicarPreferencias, guardarPreferencias, leerPreferencias } from "./accesibilidad";
import { trozos, vozLocalEnEspanol } from "./voz";

const voz = (name: string, lang: string, localService: boolean) => ({ name, lang, localService }) as SpeechSynthesisVoice;

class Frase {
  voice: SpeechSynthesisVoice | null = null;
  lang = "";
  rate = 1;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public text: string) {}
}

function sintetizador(voces: SpeechSynthesisVoice[]) {
  const dichas: Frase[] = [];
  const s = {
    getVoices: () => voces,
    speak: vi.fn((f: Frase) => dichas.push(f)),
    cancel: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  };
  vi.stubGlobal("speechSynthesis", s);
  vi.stubGlobal("SpeechSynthesisUtterance", Frase);
  return { s, dichas };
}

describe("letra y contraste", () => {
  beforeEach(() => localStorage.clear());

  it("se guardan en el equipo y se aplican a toda la página", () => {
    expect(leerPreferencias()).toEqual({ letra: "normal", contraste: false });
    guardarPreferencias({ letra: "muy-grande", contraste: true });
    expect(leerPreferencias()).toEqual({ letra: "muy-grande", contraste: true });
    expect(document.documentElement.dataset.letra).toBe("muy-grande");
    expect(document.documentElement.dataset.contraste).toBe("alto");
    guardarPreferencias({ letra: "normal", contraste: false });
    expect(document.documentElement.dataset.letra).toBeUndefined();
    expect(document.documentElement.dataset.contraste).toBeUndefined();
  });

  it("un valor guardado dañado no rompe la aplicación", () => {
    localStorage.setItem("medtender-accesibilidad", "{no es json");
    expect(() => aplicarPreferencias()).not.toThrow();
    localStorage.setItem("medtender-accesibilidad", JSON.stringify({ letra: "gigante", contraste: "si" }));
    expect(leerPreferencias()).toEqual({ letra: "normal", contraste: false });
  });

  it("sin elección propia respeta el contraste alto pedido en el sistema", () => {
    vi.stubGlobal("matchMedia", (q: string) => ({ matches: q.includes("prefers-contrast: more") }));
    expect(leerPreferencias().contraste).toBe(true);
    vi.unstubAllGlobals();
  });
});

describe("lectura en voz alta", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("solo usa voces instaladas en el equipo: las de la nube enviarían el texto fuera", () => {
    expect(vozLocalEnEspanol([voz("Nube", "es-CO", false), voz("Local US", "en-US", true)])).toBeNull();
    expect(vozLocalEnEspanol([voz("España", "es-ES", true), voz("Nube", "es-CO", false), voz("México", "es-MX", true)])?.name).toBe("México");
    expect(vozLocalEnEspanol([voz("España", "es-ES", true), voz("Colombia", "es_CO", true)])?.name).toBe("Colombia");
  });

  it("parte el texto en frases cortas sin perder nada", () => {
    const largo = "Primera frase. " + "palabra ".repeat(80).trim() + ". Última.";
    const partes = trozos(largo);
    expect(partes.every((p) => p.length <= 220)).toBe(true);
    expect(partes.join(" ").replace(/\s+/g, " ")).toBe(largo.replace(/\s+/g, " "));
  });

  it("sin una voz local en español no ofrece el botón", () => {
    sintetizador([voz("Nube", "es-CO", false)]);
    const { container } = render(<BotonLeer texto="Hola." />);
    expect(container).toBeEmptyDOMElement();
  });

  it("sin soporte del navegador tampoco", () => {
    const { container } = render(<BotonLeer texto="Hola." />);
    expect(container).toBeEmptyDOMElement();
  });

  it("lee con la voz local, se puede detener y se calla al salir", () => {
    const local = voz("Colombia", "es-CO", true);
    const { s, dichas } = sintetizador([voz("Nube", "es-CO", false), local]);
    const { unmount } = render(<BotonLeer texto="Hemoglobina 13,2. Fin." />);
    fireEvent.click(screen.getByRole("button", { name: "Escuchar" }));
    expect(dichas.length).toBeGreaterThan(0);
    expect(dichas.every((f) => f.voice === local)).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Detener la lectura" }));
    expect(s.cancel).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Escuchar" }));
    act(() => dichas[dichas.length - 1]!.onend?.());
    expect(screen.getByRole("button", { name: "Escuchar" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Escuchar" }));
    s.cancel.mockClear();
    unmount();
    expect(s.cancel).toHaveBeenCalled();
  });
});
