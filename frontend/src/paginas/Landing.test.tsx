import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const publico = vi.hoisted(() => ({ ia: null as null | { proveedor: string; respaldo: string } }));
vi.mock("../api/cliente", () => ({
  api: async () => {
    if (!publico.ia) throw new Error("sin respuesta");
    return publico.ia;
  },
}));

const { PaginaBienvenida, PaginaPersonas } = await import("./Bienvenida");
const { PaginaNoEncontrada, PaginaPrivacidad } = await import("./Legal");

const enRuta = (ui: React.ReactElement) =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );

beforeEach(() => {
  publico.ia = null;
});

describe("las páginas públicas nombran al proveedor de IA activo", () => {
  const paginas = [
    ["organizaciones", () => <PaginaBienvenida />],
    ["personas", () => <PaginaPersonas />],
    ["privacidad", () => <PaginaPrivacidad />],
  ] as const;

  it.each(paginas)("%s: con la API gratuita avisa que Google puede usar lo que recibe", async (_n, pagina) => {
    publico.ia = { proveedor: "gemini_api", respaldo: "" };
    const { container } = enRuta(pagina());
    await waitFor(() => expect(container.textContent).toMatch(/versión gratuita de Google, que puede usar lo que recibe/));
    expect(container.textContent).not.toMatch(/Vertex|Claude/);
  });

  it.each(paginas)("%s: con Vertex y respaldo nombra a los dos, sin hablar de contratos", async (_n, pagina) => {
    publico.ia = { proveedor: "vertex", respaldo: "claude" };
    const { container } = enRuta(pagina());
    await waitFor(() => expect(container.textContent).toMatch(/Gemini en Google Cloud \(Vertex AI\).*Claude, de Anthropic/));
    expect(container.textContent).not.toMatch(/gratuita|con contrato/);
  });

  it.each(paginas)("%s: si no se puede saber, no afirma nada sobre el uso de los datos", (_n, pagina) => {
    const { container } = enRuta(pagina());
    expect(container.textContent).toMatch(/Antes de aceptar el consentimiento verás cuáles son/);
    expect(container.textContent).not.toMatch(/Gemini|Claude|para entrenar|gratuita/);
  });
});

describe("portadas", () => {
  it("la de organizaciones tiene una sola acción principal arriba y la misma al cierre", () => {
    enRuta(<PaginaBienvenida />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Respuestas sobre tus expedientes de salud");
    const acciones = screen.getAllByRole("link", { name: /Ingresar a mi organización/ });
    expect(acciones).toHaveLength(4); // primera y última escena del recorrido, bloque de seguridad y cierre: todas al mismo destino
    acciones.forEach((a) => expect(a).toHaveAttribute("href", "/ingreso"));
  });

  it("la de personas ofrece crear la cuenta y enlaza a la de organizaciones", () => {
    enRuta(<PaginaPersonas />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Entiende los documentos que te entregan en el hospital");
    expect(screen.getAllByRole("link", { name: /Crear mi cuenta/ })[0]).toHaveAttribute("href", "/registro");
    expect(screen.getAllByRole("link", { name: "Para organizaciones" })[0]).toHaveAttribute("href", "/");
  });

  it("marca el ejemplo como ilustrativo y no inventa cifras ni testimonios", () => {
    enRuta(<PaginaBienvenida />);
    expect(screen.getByText(/Ejemplo ilustrativo, datos de demostración/)).toBeInTheDocument();
    expect(screen.queryByText(/clientes|testimonio|%/i)).not.toBeInTheDocument();
  });

  it("incluye el lema, las preguntas frecuentes y los enlaces legales", () => {
    enRuta(<PaginaBienvenida />);
    expect(screen.getByLabelText("Lo que prometemos")).toHaveTextContent("Una respuesta sin fuente no es una respuesta");
    expect(screen.getAllByText(/¿Dónde se guardan mis documentos\?/).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Privacidad" })).toHaveAttribute("href", "/privacidad");
    expect(screen.getByRole("link", { name: "Términos" })).toHaveAttribute("href", "/terminos");
  });
});

describe("páginas de apoyo", () => {
  it("la política de privacidad se declara borrador y menciona los 14 días de respaldos", () => {
    enRuta(<PaginaPrivacidad />);
    expect(screen.getByRole("note")).toHaveTextContent(/Borrador/);
    expect(screen.getByText(/hasta 14 días más/)).toBeInTheDocument();
  });

  it("la 404 propia da una salida", () => {
    enRuta(<PaginaNoEncontrada />);
    expect(screen.getByRole("heading", { name: "No encontramos esa página" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Volver al inicio" })).toHaveAttribute("href", "/");
  });
});
