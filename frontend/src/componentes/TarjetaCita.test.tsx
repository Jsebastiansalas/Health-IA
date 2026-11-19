import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Cita } from "../api/tipos";
import { TarjetaCita } from "./TarjetaCita";

const base: Cita = {
  documentoId: "d1",
  nombreArchivo: "Registro_INVIMA.pdf",
  tipoDocumento: "REGISTRO_SANITARIO",
  numeroAdenda: 0,
  sha256Original: "a".repeat(64),
  paginaInicio: 4,
  paginaFin: 4,
  seccion: "ANEXO 4 REGISTRO SANITARIO",
  orden: 3,
  extractoLiteral: "Registro sanitario INVIMA 2024M-0001234",
  extractoAjustado: false,
  metodoExtraccion: "OCR",
  confianzaOcr: 0.62,
  requiereVerificacionVisualOriginal: true,
  motivoVerificacionVisual: "Verifique en el PDF original de su PC: el fragmento contiene sellos o firmas.",
};

describe("TarjetaCita", () => {
  it("muestra fuente, extracto literal y la alerta probatoria", () => {
    render(<TarjetaCita cita={base} numero={1} alAbrir={() => {}} />);
    expect(screen.getByText("Registro_INVIMA.pdf")).toBeInTheDocument();
    expect(screen.getByText(/Registro sanitario · pág\. 4/)).toBeInTheDocument();
    expect(screen.getByText("«Registro sanitario INVIMA 2024M-0001234»")).toBeInTheDocument();
    expect(screen.getByText("Verificar original")).toBeInTheDocument();
    expect(screen.getByText(/OCR · confianza 62 %/)).toBeInTheDocument();
  });

  it("abre el original en la página citada", () => {
    const alAbrir = vi.fn();
    render(<TarjetaCita cita={base} numero={1} alAbrir={alAbrir} />);
    fireEvent.click(screen.getByRole("button", { name: /Abrir en mi PC · pág\. 4/ }));
    expect(alAbrir).toHaveBeenCalledWith(base);
  });

  it("no muestra el sello si no hace falta verificar", () => {
    render(
      <TarjetaCita
        cita={{ ...base, requiereVerificacionVisualOriginal: false, motivoVerificacionVisual: null, metodoExtraccion: "NATIVE", confianzaOcr: null }}
        numero={2}
        alAbrir={() => {}}
      />,
    );
    expect(screen.queryByText("Verificar original")).not.toBeInTheDocument();
  });
});
