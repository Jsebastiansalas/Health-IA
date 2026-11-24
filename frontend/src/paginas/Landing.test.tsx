import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { PaginaBienvenida, PaginaPersonas } from "./Bienvenida";
import { PaginaNoEncontrada, PaginaPrivacidad } from "./Legal";

const enRuta = (ui: React.ReactElement) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe("portadas", () => {
  it("la de organizaciones tiene una sola acción principal arriba y la misma al cierre", () => {
    enRuta(<PaginaBienvenida />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Respuestas sobre tus expedientes de salud");
    const acciones = screen.getAllByRole("link", { name: /Ingresar a mi organización/ });
    expect(acciones).toHaveLength(3); // arriba, bloque de seguridad y cierre: todas al mismo destino
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
