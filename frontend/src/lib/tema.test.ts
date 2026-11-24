import { beforeEach, describe, expect, it } from "vitest";
import { aplicarTema, temaActual, temaInicial } from "./tema";

describe("tema", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-tema");
    document.head.innerHTML = '<meta name="theme-color" content="#f4f7fa" />';
  });

  it("aplica el tema al documento, lo recuerda y avisa a la barra del navegador", () => {
    aplicarTema("oscuro");
    expect(temaActual()).toBe("oscuro");
    expect(localStorage.getItem("medtender-tema")).toBe("oscuro");
    expect(document.querySelector('meta[name="theme-color"]')?.getAttribute("content")).toBe("#000000");
  });

  it("prefiere lo guardado por el usuario al ajuste del sistema", () => {
    localStorage.setItem("medtender-tema", "claro");
    expect(temaInicial()).toBe("claro");
  });

  it("ignora un valor guardado inválido y no sigue al sistema: el inicial es el claro", () => {
    localStorage.setItem("medtender-tema", "rosa");
    expect(temaInicial()).toBe("claro");
  });
});
