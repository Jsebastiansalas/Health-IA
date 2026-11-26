import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Expediente } from "../api/tipos";

const estado = vi.hoisted(() => ({ archivo: null as File | null, descartado: 0 }));

vi.mock("../lib/compartido", () => ({
  useCompartido: () => ({ archivo: estado.archivo, cargando: false }),
  descartarCompartido: async () => {
    estado.descartado++;
  },
}));
vi.mock("../lib/consentimiento", () => ({ useConsentimiento: () => ({ bloqueado: false }) }));

const expediente = (id: string, titulo: string, extra: Partial<Expediente> = {}): Expediente => ({
  id,
  codigo_expediente: id.toUpperCase(),
  titulo,
  entidad_contratante: null,
  tipo_expediente: "AUDITORIA_CLINICA",
  estado: "ABIERTO",
  embedding_model_activo: "m",
  embedding_dimension: 768,
  created_at: "2026-11-25T00:00:00Z",
  mi_permiso: "ADMIN",
  ...extra,
});

vi.mock("../api/cliente", () => ({
  api: async () => [
    expediente("a", "Mis documentos"),
    expediente("b", "Solo lectura", { mi_permiso: "LECTOR" }),
    expediente("c", "Cerrado", { estado: "CERRADO" }),
  ],
  post: vi.fn(),
  subirDocumento: vi.fn(),
}));

const { PaginaCompartir } = await import("./Compartir");

const pintar = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <PaginaCompartir />
      </MemoryRouter>
    </QueryClientProvider>,
  );

describe("PaginaCompartir", () => {
  beforeEach(() => {
    estado.archivo = null;
    estado.descartado = 0;
  });

  it("sin archivo explica cómo compartir", () => {
    pintar();
    expect(screen.getByRole("heading", { name: "No llegó ningún archivo" })).toBeInTheDocument();
  });

  it("ofrece solo expedientes abiertos donde se puede subir y deja el archivo listo", async () => {
    estado.archivo = new File(["%PDF"], "resultado.pdf", { type: "application/pdf" });
    pintar();
    expect(screen.getByText("resultado.pdf")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: /Mis documentos/ }));
    expect(screen.queryByRole("button", { name: /Solo lectura/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Cerrado/ })).not.toBeInTheDocument();
    expect(screen.getByText(/listo para cargar/)).toBeInTheDocument();
  });

  it("cancelar borra el archivo del teléfono", async () => {
    estado.archivo = new File(["x"], "foto.jpg", { type: "image/jpeg" });
    pintar();
    fireEvent.click(screen.getByRole("button", { name: /Cancelar y borrar/ }));
    await vi.waitFor(() => expect(estado.descartado).toBe(1));
  });
});
