import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const falso = vi.hoisted(() => ({ personal: true, bloqueado: false }));

vi.mock("../api/cliente", () => ({
  api: async (ruta: string) =>
    ruta.endsWith("/documentos")
      ? []
      : {
          id: "e1",
          codigo_expediente: "EXP-MWX352NX",
          titulo: "Mis exámenes",
          entidad_contratante: null,
          tipo_expediente: "AUDITORIA_CLINICA",
          estado: "ABIERTO",
          mi_permiso: "ADMIN",
        },
}));
vi.mock("../lib/consentimiento", () => ({
  useConsentimiento: () => ({ esPersonal: falso.personal, bloqueado: falso.bloqueado, pendiente: false, correoPendiente: false }),
}));
vi.mock("../lib/useMediaQuery", () => ({ useMediaQuery: () => false }));
vi.mock("../componentes/PanelDocumentos", () => ({ PanelDocumentos: () => null }));
vi.mock("../componentes/ConsolaRag", () => ({ ConsolaRag: () => null }));
vi.mock("../componentes/Privacidad", () => ({ BotonBorrarHistorial: () => null }));

const { PaginaExpediente } = await import("./Expediente");

const pintar = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/expedientes/e1"]}>
        <Routes>
          <Route path="/expedientes/:id" element={<PaginaExpediente />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

const ruta = async () => (await screen.findByRole("navigation", { name: "Ruta" })).textContent;

describe("el expediente de una persona", () => {
  beforeEach(() => {
    falso.personal = true;
    falso.bloqueado = false;
  });

  it("la ruta muestra el nombre, no el código que la persona nunca escribió", async () => {
    pintar();
    expect(await ruta()).toContain("Mis exámenes");
    expect(await ruta()).not.toContain("EXP-MWX352NX");
    expect(screen.getByRole("button", { name: "Compartir con un cuidador" })).toBeInTheDocument();
  });

  it("no ofrece compartir mientras falte aceptar el consentimiento", async () => {
    falso.bloqueado = true;
    pintar();
    await ruta();
    expect(screen.queryByRole("button", { name: "Compartir con un cuidador" })).not.toBeInTheDocument();
  });

  it("las organizaciones siguen viendo el código y no comparten con cuidadores", async () => {
    falso.personal = false;
    pintar();
    expect(await ruta()).toContain("EXP-MWX352NX");
    expect(screen.queryByRole("button", { name: "Compartir con un cuidador" })).not.toBeInTheDocument();
  });
});
