import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const falso = vi.hoisted(() => ({
  lista: [] as unknown[],
  compartidos: [] as unknown[],
  llamadas: [] as [string, string, unknown][],
  fallo: null as null | Error,
}));

vi.mock("../api/cliente", () => ({
  api: async (ruta: string, opciones?: { method?: string }) => {
    const metodo = opciones?.method ?? "GET";
    if (metodo !== "GET") {
      falso.llamadas.push([metodo, ruta, null]);
      return undefined;
    }
    if (ruta === "/compartidos") return falso.compartidos;
    return falso.lista;
  },
  post: async (ruta: string, cuerpo: unknown) => {
    falso.llamadas.push(["POST", ruta, cuerpo]);
    if (falso.fallo) throw falso.fallo;
    return {};
  },
}));

const { CompartirExpediente, CompartidosConmigo, AvisoCompartido } = await import("./Cuidadores");

const pintar = (algo: ReactElement) =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>{algo}</MemoryRouter>
    </QueryClientProvider>,
  );

describe("compartir con un cuidador", () => {
  beforeEach(() => {
    falso.lista = [];
    falso.compartidos = [];
    falso.llamadas.length = 0;
    falso.fallo = null;
  });

  it("explica qué podrá hacer y exige confirmar antes de invitar", async () => {
    pintar(<CompartirExpediente expedienteId="e1" />);
    fireEvent.click(screen.getByRole("button", { name: "Compartir con un cuidador" }));
    expect(screen.getByText(/en ningún caso podrá borrar/i)).toBeInTheDocument();
    const invitar = screen.getByRole("button", { name: "Enviar invitación" });
    expect(invitar).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Correo de esa persona"), { target: { value: "luis@correo.co" } });
    expect(invitar).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: /tengo derecho a compartir/i }));
    fireEvent.click(invitar);
    await waitFor(() =>
      expect(falso.llamadas).toContainEqual(["POST", "/expedientes/e1/comparticiones", { correo: "luis@correo.co", permiso: "LECTOR" }]),
    );
  });

  it("permite elegir que también suba documentos y muestra el error del servidor", async () => {
    falso.fallo = new Error("Esa persona ya tiene acceso; quítalo antes de volver a invitarla");
    pintar(<CompartirExpediente expedienteId="e1" />);
    fireEvent.click(screen.getByRole("button", { name: "Compartir con un cuidador" }));
    fireEvent.change(screen.getByLabelText("Correo de esa persona"), { target: { value: "luis@correo.co" } });
    fireEvent.click(screen.getByRole("radio", { name: /ver y subir documentos/i }));
    fireEvent.click(screen.getByRole("checkbox", { name: /tengo derecho a compartir/i }));
    fireEvent.click(screen.getByRole("button", { name: "Enviar invitación" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("ya tiene acceso");
    expect(falso.llamadas[0][2]).toEqual({ correo: "luis@correo.co", permiso: "EDITOR" });
  });

  it("lista quién tiene acceso, cuándo entró y deja quitarlo", async () => {
    falso.lista = [
      { id: "c1", correo: "luis@correo.co", permiso: "LECTOR", estado: "ACEPTADA", ultimo_acceso: "2026-11-25T15:00:00Z" },
      { id: "c2", correo: "eva@correo.co", permiso: "EDITOR", estado: "PENDIENTE", ultimo_acceso: null },
    ];
    pintar(<CompartirExpediente expedienteId="e1" />);
    fireEvent.click(screen.getByRole("button", { name: "Compartir con un cuidador" }));
    expect(await screen.findByText("luis@correo.co")).toBeInTheDocument();
    expect(screen.getByText(/entró por última vez/i)).toBeInTheDocument();
    expect(screen.getByText(/invitación sin aceptar/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Quitar acceso a luis@correo.co" }));
    await waitFor(() => expect(falso.llamadas).toContainEqual(["DELETE", "/expedientes/e1/comparticiones/c1", null]));
  });

  it("el cuidador ve lo que le comparten, con el nombre de quién", async () => {
    falso.compartidos = [{ expediente_id: "e9", titulo: "Exámenes de mamá", compartido_por: "Ana Pérez", permiso: "LECTOR" }];
    pintar(<CompartidosConmigo />);
    const enlace = await screen.findByRole("link", { name: /Exámenes de mamá/ });
    expect(enlace).toHaveAttribute("href", "/expedientes/e9");
    expect(screen.getByText(/Ana Pérez/)).toBeInTheDocument();
  });

  it("sin nada compartido no ocupa espacio", () => {
    const { container } = pintar(<CompartidosConmigo />);
    expect(container).toBeEmptyDOMElement();
  });

  it("dentro de un expediente ajeno dice de quién es y permite salir tras confirmar", async () => {
    pintar(<AvisoCompartido expedienteId="e9" por="Ana Pérez" puedeSubir={false} />);
    expect(screen.getByRole("note")).toHaveTextContent("Ana Pérez te compartió este expediente");
    expect(screen.getByRole("note")).toHaveTextContent(/puedes ver y preguntar/i);
    fireEvent.click(screen.getByRole("button", { name: "Dejar de ver" }));
    expect(falso.llamadas).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Sí, dejar de verlo" }));
    await waitFor(() => expect(falso.llamadas).toContainEqual(["DELETE", "/compartidos/e9", null]));
  });
});
