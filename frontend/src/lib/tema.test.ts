import { beforeEach, describe, expect, it } from "vitest";
import { aplicarTema, temaActual, temaInicial } from "./tema";

describe("tema", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-tema");
    document.head.innerHTML = '<meta name="theme-color" content="#e6e5df" />';
  });

  it("aplica el tema al documento, lo recuerda y avisa a la barra del navegador", () => {
    aplicarTema("nocturno");
    expect(temaActual()).toBe("nocturno");
    expect(localStorage.getItem("medtender-tema")).toBe("nocturno");
    expect(document.querySelector('meta[name="theme-color"]')?.getAttribute("content")).toBe("#0f121a");
  });

  it("prefiere lo guardado por el usuario al ajuste del sistema", () => {
    localStorage.setItem("medtender-tema", "papel");
    expect(temaInicial()).toBe("papel");
  });

  it("ignora un valor guardado inválido", () => {
    localStorage.setItem("medtender-tema", "rosa");
    expect(["papel", "nocturno"]).toContain(temaInicial());
  });
});
