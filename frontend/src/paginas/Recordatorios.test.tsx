import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Recordatorio } from "../api/tipos";

const llamadas = vi.hoisted(() => ({ api: [] as [string, RequestInit | undefined][], descargas: [] as string[] }));

const base = (extra: Partial<Recordatorio>): Recordatorio => ({
  id: "r1",
  expediente_id: "e1",
  texto: "Control en 3 meses con medicina interna",
  fecha_texto: "en 3 meses",
  fecha_documento: "2025-09-15",
  fecha_propuesta: "2025-12-15",
  fecha: null,
  estado: "PROPUESTO",
  cita: { nombreArchivo: "lab.pdf", paginaInicio: 1, extractoLiteral: "Control en 3 meses" },
  avisado: false,
  ...extra,
});

const LISTA: Recordatorio[] = [
  base({}),
  base({ id: "r2", texto: "Control con cardiología", fecha_propuesta: null, fecha_documento: null }),
  base({ id: "r3", texto: "Cita con nutrición", estado: "CONFIRMADO", fecha: "2026-02-12", avisado: true }),
];

vi.mock("../api/cliente", () => ({
  api: async (ruta: string, opciones?: RequestInit) => {
    llamadas.api.push([ruta, opciones]);
    if (opciones?.method === "PATCH") {
      const { estado, fecha } = JSON.parse(String(opciones.body));
      const id = ruta.split("/").pop();
      return { ...LISTA.find((r) => r.id === id)!, estado, fecha: fecha ?? null };
    }
    return LISTA;
  },
  descargar: async (ruta: string) => {
    llamadas.descargas.push(ruta);
    return new Blob(["BEGIN:VCALENDAR"], { type: "text/calendar" });
  },
}));

const { PaginaRecordatorios } = await import("./Recordatorios");

const pintar = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <PaginaRecordatorios />
    </QueryClientProvider>,
  );

describe("PaginaRecordatorios", () => {
  beforeEach(() => {
    llamadas.api.length = 0;
    llamadas.descargas.length = 0;
  });

  it("separa por confirmar y próximos, con la fuente de cada uno y sin recordatorios de tomas", async () => {
    pintar();
    const porConfirmar = await screen.findByRole("region", { name: "Por confirmar" });
    expect(within(porConfirmar).getByText("Control en 3 meses con medicina interna")).toBeInTheDocument();
    expect(within(porConfirmar).getAllByText(/Según lab.pdf, pág. 1/).length).toBeGreaterThan(0);
    expect(within(porConfirmar).getByText(/pon tú la fecha/)).toBeInTheDocument();
    const proximos = screen.getByRole("region", { name: "Próximos" });
    expect(within(proximos).getByText("Cita con nutrición")).toBeInTheDocument();
    expect(within(proximos).getByText("Aviso enviado")).toBeInTheDocument();
    expect(screen.getByText(/No creamos recordatorios para tomar medicamentos/)).toBeInTheDocument();
  });

  it("confirma con la fecha propuesta, exige fecha cuando no la hay y descarga el calendario", async () => {
    pintar();
    const porConfirmar = await screen.findByRole("region", { name: "Por confirmar" });
    const [primera, segunda] = within(porConfirmar).getAllByRole("listitem");
    expect(within(segunda!).getByRole("button", { name: "Confirmar" })).toBeDisabled();

    fireEvent.click(within(primera!).getByRole("button", { name: "Confirmar" }));
    await waitFor(() => expect(llamadas.api.some(([r, o]) => r === "/recordatorios/r1" && o?.method === "PATCH")).toBe(true));
    const [, opciones] = llamadas.api.find(([r]) => r === "/recordatorios/r1")!;
    expect(JSON.parse(String(opciones!.body))).toEqual({ estado: "CONFIRMADO", fecha: "2025-12-15" });

    globalThis.URL.createObjectURL = vi.fn(() => "blob:x");
    globalThis.URL.revokeObjectURL = vi.fn();
    const proximos = screen.getByRole("region", { name: "Próximos" });
    // al confirmarlo, r1 ya está en «Próximos»; se descarga el de la cita con nutrición
    const nutricion = within(proximos).getByText("Cita con nutrición").closest("li")!;
    fireEvent.click(within(nutricion).getByRole("button", { name: /Añadir a mi calendario/ }));
    await waitFor(() => expect(llamadas.descargas).toContain("/recordatorios/r3/calendario.ics"));
  });
});
