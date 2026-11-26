import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { activarRastreo, limpiar } from "./errores";

/** El rastreo de errores no puede llevarse datos de salud: se revisa lo que de verdad envía el navegador. */
describe("rastreo de errores de la web", () => {
  const enviado: string[] = [];

  beforeAll(async () => {
    vi.stubGlobal("fetch", async (_url: string, opciones: { body?: unknown }) => {
      const cuerpo = opciones.body;
      enviado.push(typeof cuerpo === "string" ? cuerpo : new TextDecoder().decode(cuerpo as Uint8Array));
      return new Response("{}", { status: 200 });
    });
    window.history.pushState({}, "", "/expedientes/historia-de-ana?pregunta=que-tomo");
    document.title = "Historia de Ana";
    await activarRastreo("http://claveinventada@errores.prueba/1");
  });

  afterAll(() => vi.unstubAllGlobals());

  it("envía el tipo del error y por dónde pasó, y nada de la persona ni de la página", async () => {
    const Sentry = await import("@sentry/browser");
    Sentry.setUser({ email: "ana@correo.co" });
    Sentry.setTag("pregunta", "¿qué tomo?");
    Sentry.addBreadcrumb({ message: "clic en «Resultados de Ana»" });
    function fallaAlPintar() {
      throw new TypeError("No se pudo leer la hemoglobina de Ana Pérez (13,2 g/dL)");
    }
    try {
      fallaAlPintar();
    } catch (e) {
      Sentry.captureException(e);
    }
    await Sentry.flush(2000);

    const todo = enviado.join("\n");
    expect(todo).toContain("TypeError");
    expect(todo).toContain("fallaAlPintar");
    for (const prohibido of ["Ana", "ana@correo.co", "hemoglobina", "13,2", "tomo", "historia-de-ana", "Mozilla"]) {
      expect(todo).not.toContain(prohibido);
    }
  });

  it("deja el nombre del archivo sin dirección ni parámetros", () => {
    const limpio = limpiar({
      exception: { values: [{ type: "Error", value: "secreto", stacktrace: { frames: [{ filename: "https://sitio.co/assets/index-a1.js?token=abc#x", function: "f", lineno: 3, colno: 9, vars: { nombre: "Ana" } }] } }] },
      request: { url: "https://sitio.co/expedientes/1" },
    } as never);
    expect(limpio?.exception?.values?.[0]).toEqual({
      type: "Error",
      value: "",
      stacktrace: { frames: [{ filename: "/assets/index-a1.js", function: "f", lineno: 3, colno: 9, in_app: undefined }] },
    });
    expect(limpio?.request).toBeUndefined();
  });

  it("sin excepción no envía nada y sin DSN no se activa", async () => {
    expect(limpiar({ message: "algo sobre Ana" } as never)).toBeNull();
    expect(await activarRastreo(undefined)).toBe(false);
  });
});
