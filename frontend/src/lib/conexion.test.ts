import { describe, expect, it } from "vitest";
import { conviveConDatosLimitados } from "./conexion";

const con = (connection: unknown) => conviveConDatosLimitados({ connection } as unknown as Navigator);

describe("datos limitados", () => {
  it("en datos móviles, con ahorro de datos o red lenta se muestran imágenes fijas", () => {
    expect(con({ saveData: true, effectiveType: "4g" })).toBe(true);
    expect(con({ type: "cellular", effectiveType: "4g" })).toBe(true);
    for (const effectiveType of ["slow-2g", "2g", "3g"]) expect(con({ effectiveType })).toBe(true);
  });

  it("con buena conexión, o si el navegador no lo dice, se muestran los videos", () => {
    expect(con({ effectiveType: "4g", saveData: false })).toBe(false);
    expect(con({ type: "wifi", effectiveType: "4g" })).toBe(false);
    expect(con(undefined)).toBe(false);
  });
});
