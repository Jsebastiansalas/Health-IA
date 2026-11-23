import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CitaFicha, RespuestaConsulta } from "../api/tipos";
import { CruceMedicamentos } from "./CruceMedicamentos";

const ficha: CitaFicha = {
  tipo: "FICHA_TECNICA",
  id: "F1",
  medicamento: "IBUPROFENO FALSO 400 MG",
  principioActivo: "ibuprofeno",
  registro: "111",
  seccion: "4.3",
  titulo: "Contraindicaciones",
  extractoLiteral: "- en pacientes con úlcera gástrica",
  extractoTruncado: false,
  fuente: { conjunto: "Ficha técnica (CIMA)", datasetId: "111", enlace: "https://cima.aemps.es/x", cargadoAt: null, licencia: "AEMPS" },
};

const base: RespuestaConsulta = {
  consultaId: "c1",
  modo: "cruce",
  respuestaAnalitica: "Medicamentos de tus documentos.",
  medicamentos: [
    { nombre: "Ibuprofeno", cita: 1, ficha: true },
    { nombre: "Losartán", cita: 3, ficha: false },
  ],
  diagnosticos: [{ texto: "úlcera gástrica", cita: 2 }],
  alergias: [{ texto: "penicilina", cita: 4 }],
  advertencias: [
    {
      texto: "La ficha de ibuprofeno lo contraindica en pacientes con úlcera gástrica; tu documento menciona úlcera gástrica.",
      medicamento: "Ibuprofeno",
      dato: "úlcera gástrica",
      citaMedicamento: 1,
      citaDato: 2,
      ficha: 1,
    },
  ],
  sinFicha: ["Losartán"],
  fichas: [ficha],
  avisoGeneral: "No indica qué medicamento tomar.",
  sinEvidencia: false,
  alertas: [],
  citas: [],
  modeloEmbeddings: "gemini-embedding-001",
  modeloLlm: "gemini",
  fragmentosRecuperados: 4,
  latenciaMs: 900,
};

describe("CruceMedicamentos", () => {
  it("muestra los medicamentos, la advertencia con sus dos citas y la ficha citada", () => {
    render(<CruceMedicamentos respuesta={base} alIrACita={() => {}} />);
    expect(screen.getByRole("heading", { name: /Medicamentos que aparecen en tus documentos/ })).toBeInTheDocument();
    expect(screen.getByText(/\(sin ficha técnica cargada\)/)).toBeInTheDocument();
    expect(screen.getByText(/lo contraindica en pacientes con úlcera gástrica/)).toBeInTheDocument();
    expect(screen.getByText(/Contraindicaciones · sección 4\.3/)).toBeInTheDocument();
    expect(screen.getByText(/Sin ficha técnica cargada: Losartán/)).toBeInTheDocument();
    expect(screen.getByText(/No indica qué medicamento tomar/)).toBeInTheDocument();
  });

  it("las citas al documento abren su tarjeta", () => {
    const alIr = vi.fn();
    render(<CruceMedicamentos respuesta={base} alIrACita={alIr} />);
    fireEvent.click(screen.getAllByRole("button", { name: "Ir a la cita 2" })[0]!);
    expect(alIr).toHaveBeenCalledWith(2);
  });

  it("sin advertencias dice que eso no significa que no existan y remite al médico", () => {
    render(<CruceMedicamentos respuesta={{ ...base, advertencias: [], fichas: [] }} alIrACita={() => {}} />);
    expect(screen.getByText(/Eso no significa que no existan/)).toBeInTheDocument();
    expect(screen.queryByText(/Contraindicaciones · sección/)).not.toBeInTheDocument();
  });

  it("sin medicamentos en los documentos lo dice y no pinta secciones", () => {
    render(
      <CruceMedicamentos
        respuesta={{ ...base, sinEvidencia: true, medicamentos: [], respuestaAnalitica: "No encontré medicamentos escritos." }}
        alIrACita={() => {}}
      />,
    );
    expect(screen.getByText("Sin medicamentos en tus documentos")).toBeInTheDocument();
    expect(screen.queryByText(/Lo que advierten/)).not.toBeInTheDocument();
  });
});
