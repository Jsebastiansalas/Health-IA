import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const falso = vi.hoisted(() => ({
  descargas: [] as [string, unknown][],
  cambios: [] as unknown[],
  falloDescarga: null as null | Error,
  meses: null as null | number,
}));

vi.mock("../api/cliente", () => ({
  api: async (ruta: string, opciones?: { method?: string; body?: string }) => {
    if (ruta !== "/cuenta/retencion") throw new Error(`ruta inesperada ${ruta}`);
    if (opciones?.method === "PUT") {
      const cuerpo = JSON.parse(opciones.body ?? "{}") as { meses: number | null };
      falso.cambios.push(cuerpo);
      falso.meses = cuerpo.meses;
      return { meses: cuerpo.meses, borradas: 3 };
    }
    return { meses: falso.meses, se_borrarian: { "3": 5, "6": 3, "12": 1, "24": 0 } };
  },
  descargar: async (ruta: string, cuerpo: unknown) => {
    falso.descargas.push([ruta, cuerpo]);
    if (falso.falloDescarga) throw falso.falloDescarga;
    return new Blob(["zip"]);
  },
}));

const { PaginaMisDatos } = await import("./MisDatos");

const pintar = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <PaginaMisDatos />
      </MemoryRouter>
    </QueryClientProvider>,
  );

describe("mis datos", () => {
  beforeEach(() => {
    falso.descargas.length = 0;
    falso.cambios.length = 0;
    falso.falloDescarga = null;
    falso.meses = null;
    URL.createObjectURL = vi.fn(() => "blob:zip");
    URL.revokeObjectURL = vi.fn();
  });

  it("descarga el ZIP con la contraseña y avisa que lleva información de salud", async () => {
    const clic = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    pintar();
    expect(screen.getByText(/contiene información de salud/i)).toBeInTheDocument();
    const boton = screen.getByRole("button", { name: "Descargar mis datos" });
    expect(boton).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Contraseña"), { target: { value: "Clave-Segura-123" } });
    fireEvent.click(boton);
    await waitFor(() => expect(clic).toHaveBeenCalled());
    expect(falso.descargas).toEqual([["/cuenta/exportar", { password: "Clave-Segura-123" }]]);
    expect(screen.getByLabelText("Contraseña")).toHaveValue("");
    clic.mockRestore();
  });

  it("muestra por qué no se pudo descargar", async () => {
    falso.falloDescarga = new Error("Contraseña incorrecta");
    pintar();
    fireEvent.change(screen.getByLabelText("Contraseña"), { target: { value: "otra" } });
    fireEvent.click(screen.getByRole("button", { name: "Descargar mis datos" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Contraseña incorrecta");
  });

  it("antes de borrar dice cuántas respuestas se pierden y no envía nada sin confirmar", async () => {
    pintar();
    expect(await screen.findByRole("radio", { name: "Conservar todo" })).toBeChecked();
    fireEvent.click(screen.getByRole("radio", { name: "6 meses" }));
    expect(screen.getByRole("status")).toHaveTextContent(/Se borrarán ahora 3 respuestas guardadas.*no se puede deshacer/i);
    expect(falso.cambios).toEqual([]);

    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.getByRole("radio", { name: "Conservar todo" })).toBeChecked();
    expect(falso.cambios).toEqual([]);

    fireEvent.click(screen.getByRole("radio", { name: "6 meses" }));
    fireEvent.click(screen.getByRole("button", { name: "Borrar y guardar" }));
    await waitFor(() => expect(falso.cambios).toEqual([{ meses: 6 }]));
  });

  it("si no hay nada antiguo, guarda sin hablar de borrar", async () => {
    pintar();
    fireEvent.click(await screen.findByRole("radio", { name: "24 meses" }));
    expect(screen.getByRole("status")).toHaveTextContent(/A partir de ahora se borrará solo lo que tenga más de 24 meses/);
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(falso.cambios).toEqual([{ meses: 24 }]));
  });
});
