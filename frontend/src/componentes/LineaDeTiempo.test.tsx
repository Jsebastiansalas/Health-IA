import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { RespuestaConsulta } from "../api/tipos";
import { LineaDeTiempo } from "./LineaDeTiempo";

const base: RespuestaConsulta = {
  consultaId: "c1",
  modo: "cronologia",
  respuestaAnalitica: "Línea de tiempo de tus documentos.",
  sinEvidencia: false,
  alertas: ["Se omitieron 2 dato(s) que no se pudieron comprobar contra el texto de tus documentos."],
  citas: [],
  modeloEmbeddings: "m",
  modeloLlm: "x",
  fragmentosRecuperados: 4,
  latenciaMs: 10,
  avisoGeneral: "Esta línea de tiempo ordena lo que dicen tus documentos. No interpreta tus resultados.",
  guardada: true,
  generadaAt: "2026-11-25T10:00:00Z",
  eventos: [
    { fecha: "2025-03-12", fechaTexto: "12/03/2025", tipo: "EXAMEN", texto: "Laboratorio clínico", cita: 1 },
    { fecha: null, fechaTexto: "03/12", tipo: "CONTROL", texto: "Control con medicina interna", cita: 2 },
    { fecha: null, fechaTexto: "en 3 meses", referencia: "2025-09-15", tipo: "CONTROL", texto: "Control en 3 meses", cita: 3 },
  ],
  analitos: [
    {
      clave: "hemoglobina",
      nombre: "Hemoglobina",
      unidades: ["g/dL"],
      comparable: true,
      valores: [
        { fecha: "2025-03-12", fechaTexto: "12/03/2025", valor: 13.2, valorTexto: "13,2", unidad: "g/dL", rango: "12,0 - 15,5", marca: null, cita: 1 },
        { fecha: "2025-09-15", fechaTexto: "15/09/2025", valor: 12.1, valorTexto: "12,1", unidad: "g/dL", rango: "12,0 - 15,5", marca: null, cita: 3 },
      ],
    },
    {
      clave: "colesterol ldl",
      nombre: "Colesterol LDL",
      unidades: ["mg/dL"],
      comparable: true,
      valores: [{ fecha: "2025-03-12", fechaTexto: "12/03/2025", valor: 160, valorTexto: "160", unidad: "mg/dL", rango: "< 130", marca: "ALTO", cita: 1 }],
    },
  ],
};

describe("LineaDeTiempo", () => {
  it("muestra los eventos, la evolución con su gráfica y los demás resultados con su cita", () => {
    const alIrACita = vi.fn();
    render(<LineaDeTiempo respuesta={base} alIrACita={alIrACita} />);
    expect(screen.getByRole("heading", { name: /Lo que pasó/ })).toBeInTheDocument();
    expect(screen.getByText("Laboratorio clínico")).toBeInTheDocument();
    // una fecha que no se entiende se muestra tal como está escrita
    expect(screen.getByText("03/12")).toBeInTheDocument();
    expect(screen.getAllByText(/Fecha tal como la escribe el documento/)).toHaveLength(1);
    // un control relativo se muestra junto a la fecha del documento que lo indica
    expect(screen.getByText(/en 3 meses · indicado en el documento del/)).toBeInTheDocument();

    const evolucion = screen.getByRole("heading", { name: /Cómo cambiaron/ }).closest("section")!;
    expect(within(evolucion).getByRole("figure", { name: /Evolución de Hemoglobina/ })).toBeInTheDocument();
    expect(within(evolucion).getByText(/rango impreso en el documento/)).toBeInTheDocument();

    // el LDL tiene una sola medición: va a «Otros resultados», sin gráfica, con la marca impresa
    const otros = screen.getByRole("heading", { name: /Otros resultados/ }).closest("section")!;
    expect(within(otros).queryByRole("figure")).not.toBeInTheDocument();
    expect(within(otros).getByTitle("Marca impresa en el documento")).toHaveTextContent("ALTO");

    fireEvent.click(within(evolucion).getByRole("button", { name: /12,1.*Abrir la cita 3/ }));
    expect(alIrACita).toHaveBeenCalledWith(3);
  });

  it("dice que no interpreta, muestra las alertas y ofrece volver a armarla", () => {
    const alRehacer = vi.fn();
    render(<LineaDeTiempo respuesta={base} alIrACita={() => {}} alRehacer={alRehacer} />);
    expect(screen.getByText(/No interpreta tus resultados/)).toBeInTheDocument();
    expect(screen.getByText(/Se omitieron 2 dato/)).toBeInTheDocument();
    expect(screen.getByText(/tus documentos no cambiaron/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Volver a armarla" }));
    expect(alRehacer).toHaveBeenCalledOnce();
  });

  it("sin fechas ni resultados lo dice", () => {
    render(
      <LineaDeTiempo
        respuesta={{ ...base, sinEvidencia: true, eventos: [], analitos: [], respuestaAnalitica: "No encontré fechas." }}
        alIrACita={() => {}}
      />,
    );
    expect(screen.getByText(/Sin fechas ni resultados/)).toBeInTheDocument();
    expect(screen.getByText("No encontré fechas.")).toBeInTheDocument();
  });
});
