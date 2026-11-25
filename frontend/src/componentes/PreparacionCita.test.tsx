import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Cita, RespuestaConsulta } from "../api/tipos";

const armar = vi.hoisted(() => vi.fn(async () => new Blob(["%PDF"], { type: "application/pdf" })));
vi.mock("../lib/pdfCita", () => ({ armarPdfCita: armar }));

const { PreparacionCita } = await import("./PreparacionCita");

const cita = (n: number): Cita => ({
  documentoId: `d${n}`,
  nombreArchivo: `lab_${n}.pdf`,
  tipoDocumento: "HISTORIA_CLINICA",
  numeroAdenda: 0,
  sha256Original: "0".repeat(64),
  paginaInicio: 1,
  paginaFin: 1,
  seccion: "",
  orden: n,
  extractoLiteral: `extracto ${n}`,
  extractoAjustado: false,
  metodoExtraccion: "NATIVE",
  confianzaOcr: null,
  requiereVerificacionVisualOriginal: false,
  motivoVerificacionVisual: null,
});

export const resumen: RespuestaConsulta = {
  consultaId: "p1",
  modo: "preparacion",
  respuestaAnalitica: "Resumen para tu próxima cita.",
  avisoGeneral: "Este resumen junta lo que dicen tus documentos. No es un diagnóstico.",
  sinEvidencia: false,
  alertas: ["Se descartaron 1 pregunta(s) sugerida(s) que afirmaban algo que tus documentos no dicen."],
  citas: [cita(1), cita(2), cita(3)],
  modeloEmbeddings: "m",
  modeloLlm: "x",
  fragmentosRecuperados: 3,
  latenciaMs: 10,
  eventos: [{ fecha: "2025-09-15", fechaTexto: "15/09/2025", tipo: "EXAMEN", texto: "Resultados de laboratorio: Hb.", cita: 2 }],
  cambios: [
    {
      nombre: "Hemoglobina",
      mediciones: 2,
      desde: { fecha: "2025-03-12", valorTexto: "13,2", unidad: "g/dL", marca: null, cita: 1 },
      hasta: { fecha: "2025-09-15", valorTexto: "12,1", unidad: "g/dL", marca: null, cita: 2 },
    },
  ],
  medicamentos: [{ nombre: "Atorvastatina", cita: 3 }],
  diagnosticos: [{ texto: "dislipidemia", cita: 3 }],
  alergias: [],
  preguntas: ["¿Cuándo debo repetir el perfil lipídico?", "¿Qué significa la marca ALTO?"],
};

describe("PreparacionCita", () => {
  beforeEach(() => armar.mockClear());

  it("muestra el resumen con sus citas y lleva al PDF las preguntas tal como las deja la persona", async () => {
    const alIrACita = vi.fn();
    render(<PreparacionCita respuesta={resumen} alIrACita={alIrACita} />);
    expect(screen.getByText(/No es un diagnóstico/)).toBeInTheDocument();
    expect(screen.getByText("Hemoglobina")).toBeInTheDocument();
    expect(screen.getByText("Atorvastatina")).toBeInTheDocument();
    expect(screen.getByText(/Se descartaron 1 pregunta/)).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Ir a la cita 3" })[0]!);
    expect(alIrACita).toHaveBeenCalledWith(3);

    // editar, quitar y agregar
    fireEvent.change(screen.getByLabelText("Pregunta 1"), { target: { value: "¿Cuándo repito el examen?" } });
    fireEvent.click(screen.getByRole("button", { name: "Quitar la pregunta 2" }));
    fireEvent.change(screen.getByLabelText("Nueva pregunta"), { target: { value: "¿Puedo hacer ejercicio?" } });
    fireEvent.click(screen.getByRole("button", { name: /Agregar/ }));

    globalThis.URL.createObjectURL = vi.fn(() => "blob:x");
    globalThis.URL.revokeObjectURL = vi.fn();
    fireEvent.click(screen.getByRole("button", { name: /Descargar PDF/ }));
    await waitFor(() => expect(armar).toHaveBeenCalledOnce());
    expect(armar).toHaveBeenCalledWith(resumen, ["¿Cuándo repito el examen?", "¿Puedo hacer ejercicio?"]);
    expect(screen.getByText(/no se guarda en el servidor/)).toBeInTheDocument();
  });

  it("sin documentos lo dice y no ofrece PDF", () => {
    render(<PreparacionCita respuesta={{ ...resumen, sinEvidencia: true, respuestaAnalitica: "Todavía no hay documentos." }} alIrACita={() => {}} />);
    expect(screen.getByText("Todavía no hay documentos.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Descargar PDF/ })).not.toBeInTheDocument();
  });
});
