import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const falso = vi.hoisted(() => ({ personal: true, expedientes: [] as unknown[], creados: [] as Record<string, unknown>[] }));

vi.mock("../api/cliente", () => ({
  api: async (ruta: string) => (ruta.startsWith("/expedientes") ? falso.expedientes : []),
  post: async (_ruta: string, cuerpo: Record<string, unknown>) => {
    falso.creados.push(cuerpo);
    return { id: "e1", codigo_expediente: cuerpo.codigo_expediente };
  },
}));
vi.mock("../sesion", () => ({ useSesion: () => ({ usuario: { nombre_completo: "Ana Pérez", rol_global: "ADMIN_TENANT" } }) }));
vi.mock("../lib/consentimiento", () => ({ useConsentimiento: () => ({ esPersonal: falso.personal }) }));

const { PaginaExpedientes } = await import("./Expedientes");

const pintar = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <PaginaExpedientes />
      </MemoryRouter>
    </QueryClientProvider>,
  );

const EXPEDIENTE = {
  id: "e1",
  codigo_expediente: "EXP-ABC123",
  titulo: "Mis exámenes",
  entidad_contratante: null,
  tipo_expediente: "AUDITORIA_CLINICA",
  estado: "ABIERTO",
  created_at: "2026-11-20T10:00:00Z",
  mi_permiso: "ADMIN",
};

describe("expedientes de una persona", () => {
  beforeEach(() => {
    falso.personal = true;
    falso.expedientes = [];
    falso.creados.length = 0;
  });

  it("no habla de licitaciones y crea el expediente solo con un nombre", async () => {
    const { container } = pintar();
    expect(await screen.findByText(/sube tus resultados, fórmulas u órdenes/i)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/pliego|adenda|licitaci/i);
    fireEvent.click(screen.getByRole("button", { name: "Abrir el primer expediente" }));
    expect(screen.queryByLabelText("Código")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Entidad contratante")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Tipo de expediente")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("¿Cómo quieres llamarlo?"), { target: { value: "Exámenes de mamá" } });
    fireEvent.click(screen.getByRole("button", { name: "Crear expediente" }));
    await waitFor(() => expect(falso.creados).toHaveLength(1));
    expect(falso.creados[0]).toMatchObject({ titulo: "Exámenes de mamá", tipo_expediente: "AUDITORIA_CLINICA", entidad_contratante: null });
    expect(falso.creados[0]!.codigo_expediente).toMatch(/^EXP-[0-9A-Z]+$/);
  });

  it("en la lista no muestra entidad ni tipo", async () => {
    falso.expedientes = [EXPEDIENTE];
    const { container } = pintar();
    expect(await screen.findByText("Mis exámenes")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/Entidad no registrada|Contratante/);
  });

  it("las organizaciones conservan su formulario completo", async () => {
    falso.personal = false;
    pintar();
    fireEvent.click(await screen.findByRole("button", { name: "Abrir el primer expediente" }));
    expect(screen.getByLabelText("Código")).toBeInTheDocument();
    expect(screen.getByLabelText("Entidad contratante")).toBeInTheDocument();
    expect(screen.getByLabelText("Tipo de expediente")).toBeInTheDocument();
  });
});
