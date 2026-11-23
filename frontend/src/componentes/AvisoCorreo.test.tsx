import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AvisoCorreo } from "./AvisoCorreo";

describe("AvisoCorreo", () => {
  it("explica que no se puede usar la cuenta hasta confirmar el correo y permite reenviar el enlace", () => {
    const alReenviar = vi.fn();
    render(<AvisoCorreo reenviando={false} reenviado={false} alReenviar={alReenviar} />);
    expect(screen.getByRole("heading", { name: "Confirma tu correo" })).toBeInTheDocument();
    expect(screen.getByText(/no puedes subir documentos ni hacer consultas/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reenviar enlace" }));
    expect(alReenviar).toHaveBeenCalledOnce();
  });

  it("confirma el reenvío y muestra el error del servidor, como el límite de envíos", () => {
    const { rerender } = render(<AvisoCorreo reenviando={false} reenviado alReenviar={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent("Enviamos un enlace nuevo.");
    rerender(<AvisoCorreo reenviando={false} reenviado={false} error="Demasiadas solicitudes." alReenviar={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Demasiadas solicitudes.");
  });
});
