import { describe, expect, it } from "vitest";
import type { RespuestaConsulta } from "../api/tipos";
import { armarPdfCita, fuente } from "./pdfCita";

const r = {
  consultaId: "p1",
  respuestaAnalitica: "",
  sinEvidencia: false,
  alertas: [],
  modeloEmbeddings: "m",
  modeloLlm: null,
  fragmentosRecuperados: 0,
  latenciaMs: 0,
  avisoGeneral: "No es un diagnostico.",
  citas: [{ nombreArchivo: "lab_marzo.pdf", paginaInicio: 2, paginaFin: 3 }],
  eventos: [{ fecha: "2025-03-12", fechaTexto: "12/03/2025", tipo: "EXAMEN", texto: "Laboratorio", cita: 1 }],
  cambios: [],
  medicamentos: [],
  diagnosticos: [],
  alergias: [],
} as unknown as RespuestaConsulta;

describe("PDF de «Preparar mi cita»", () => {
  it("cita archivo y páginas", () => {
    expect(fuente(r.citas[0])).toBe("lab_marzo.pdf, pág. 2–3");
  });

  it("arma un PDF con el resumen, las preguntas y las fuentes", async () => {
    const blob = await armarPdfCita(r, ["¿Cuando repito el examen?"]);
    expect(blob.type).toBe("application/pdf");
    const texto = await blob.text();
    expect(texto.startsWith("%PDF")).toBe(true);
    for (const t of ["Resumen para mi cita", "Preguntas para mi m", "Cuando repito el examen", "lab_marzo.pdf", "Fuentes"]) {
      expect(texto).toContain(t);
    }
  });
});
