import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { RespuestaConsulta } from "../api/tipos";
import { ExplicacionDocumento } from "./ExplicacionDocumento";

const base: RespuestaConsulta = {
  consultaId: "c1",
  modo: "explicar",
  respuestaAnalitica: "Es un examen de sangre.",
  deQueTrata: "Es un examen de laboratorio con valores de sangre.",
  hallazgos: [
    { texto: "La hemoglobina es 13,2.", cita: 1 },
    { texto: "Piden un control en un mes.", cita: 2 },
  ],
  terminos: [{ termino: "Hemoglobina", explicacion: "Proteína de la sangre que lleva oxígeno." }],
  senalesDeAlarma: [],
  preguntasParaElMedico: ["¿Qué significa mi valor de LDL?"],
  avisoGeneral: "Esta explicación es informativa, no un diagnóstico.",
  sinEvidencia: false,
  alertas: [],
  citas: [],
  modeloEmbeddings: "gemini-embedding-001",
  modeloLlm: "gemini",
  fragmentosRecuperados: 2,
  latenciaMs: 900,
};

describe("ExplicacionDocumento", () => {
  it("separa lo que dice el documento de lo que significan los términos, y rotula la segunda capa", () => {
    render(<ExplicacionDocumento respuesta={base} alIrACita={() => {}} />);
    expect(screen.getByRole("heading", { name: "De qué trata" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Lo que dice el documento" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Qué significan estos términos/ })).toBeInTheDocument();
    expect(screen.getByText(/no es un diagnóstico ni habla de tu caso/)).toBeInTheDocument();
    expect(screen.getByText("Hemoglobina")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Preguntas para llevarle a tu médico/ })).toBeInTheDocument();
    expect(screen.getByText(/no un diagnóstico/)).toBeInTheDocument();
  });

  it("cada hallazgo lleva su número de cita y lo abre", () => {
    const alIrACita = vi.fn();
    render(<ExplicacionDocumento respuesta={base} alIrACita={alIrACita} />);
    fireEvent.click(screen.getByRole("button", { name: "Ir a la cita 2" }));
    expect(alIrACita).toHaveBeenCalledWith(2);
  });

  it("las señales de alarma solo aparecen cuando el documento las marca", () => {
    const { rerender } = render(<ExplicacionDocumento respuesta={base} alIrACita={() => {}} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    rerender(<ExplicacionDocumento respuesta={{ ...base, senalesDeAlarma: ["Valor crítico de potasio"] }} alIrACita={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Valor crítico de potasio");
    expect(screen.getByRole("alert")).toHaveTextContent("123");
  });

  it("sin evidencia no muestra términos ni preguntas del modelo", () => {
    render(
      <ExplicacionDocumento
        respuesta={{ ...base, sinEvidencia: true, deQueTrata: "", hallazgos: [], terminos: [], preguntasParaElMedico: [] }}
        alIrACita={() => {}}
      />,
    );
    expect(screen.getByText("Sin evidencia suficiente")).toBeInTheDocument();
    expect(screen.queryByText(/Qué significan/)).not.toBeInTheDocument();
    expect(screen.getByText(/foto más nítida/)).toBeInTheDocument();
  });
});
