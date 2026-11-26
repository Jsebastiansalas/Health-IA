import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const falso = vi.hoisted(() => ({ llamadas: [] as unknown[], fallo: null as null | Error }));

vi.mock("../api/cliente", () => ({
  post: async (ruta: string, cuerpo: unknown) => {
    falso.llamadas.push([ruta, cuerpo]);
    if (falso.fallo) throw falso.fallo;
    return { expediente_id: "e9", titulo: "Exámenes de mamá", compartido_por: "Ana Pérez" };
  },
}));

const { PaginaInvitacion } = await import("./Invitacion");

const pintar = (ruta: string, conSesion: boolean) =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[ruta]}>
        <Routes>
          <Route path="/invitacion" element={<PaginaInvitacion conSesion={conSesion} />} />
          <Route path="/expedientes/:id" element={<p>expediente abierto</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

describe("aceptar una invitación", () => {
  beforeEach(() => {
    falso.llamadas.length = 0;
    falso.fallo = null;
  });

  it("no acepta sola: la persona decide, y al aceptar entra al expediente", async () => {
    pintar("/invitacion?token=abc", true);
    expect(falso.llamadas).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Aceptar invitación" }));
    expect(await screen.findByText("expediente abierto")).toBeInTheDocument();
    expect(falso.llamadas).toEqual([["/invitaciones/aceptar", { token: "abc" }]]);
  });

  it("explica el rechazo sin salir de la página", async () => {
    falso.fallo = new Error("El enlace no es válido para esta cuenta o ya venció.");
    pintar("/invitacion?token=abc", true);
    fireEvent.click(screen.getByRole("button", { name: "Aceptar invitación" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("no es válido para esta cuenta");
  });

  it("sin sesión pide entrar con el mismo correo y volver al enlace, sin gastar la invitación", async () => {
    pintar("/invitacion?token=abc", false);
    expect(screen.getByText(/con el mismo correo/i)).toBeInTheDocument();
    expect(screen.getByText(/vuelve a abrir el enlace/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ingresar" })).toHaveAttribute("href", "/ingreso");
    expect(screen.getByRole("link", { name: "Crear mi cuenta" })).toHaveAttribute("href", "/registro");
    expect(screen.queryByRole("button", { name: "Aceptar invitación" })).not.toBeInTheDocument();
    await waitFor(() => expect(falso.llamadas).toHaveLength(0));
  });

  it("un enlace incompleto no ofrece aceptar", () => {
    pintar("/invitacion", true);
    expect(screen.getByRole("alert")).toHaveTextContent(/enlace está incompleto/i);
    expect(screen.queryByRole("button", { name: "Aceptar invitación" })).not.toBeInTheDocument();
  });
});
