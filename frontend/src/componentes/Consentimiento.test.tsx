import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AvisoSalud, AvisoUrgencia } from "./AvisoSalud";
import { Consentimiento } from "./Consentimiento";

describe("Consentimiento", () => {
  it("explica qué se envía, a quién y cómo borrar, y deja aceptar", () => {
    const alAceptar = vi.fn();
    render(<Consentimiento version="2026-11-v4" aceptando={false} alAceptar={alAceptar} />);
    expect(screen.getByRole("heading", { name: /antes de usar tus documentos de salud/i })).toBeInTheDocument();
    expect(screen.getByText(/Gemini en Google Cloud \(Vertex AI\) y, solo si ese servicio falla, Claude de Anthropic/)).toBeInTheDocument();
    expect(screen.getByText(/Ninguno de los dos usa lo que les enviamos para entrenar sus modelos/)).toBeInTheDocument();
    expect(screen.queryByText(/versión gratuita/)).not.toBeInTheDocument();
    expect(screen.getByText(/pruebas cerradas: puede equivocarse/i)).toBeInTheDocument();
    expect(screen.getByText(/copias de seguridad conservan los datos hasta 14 días más/i)).toBeInTheDocument();
    expect(screen.getByText(/sin fecha de vencimiento/i)).toBeInTheDocument();
    expect(screen.getByText(/documentos de otra persona, declaras que tienes derecho/i)).toBeInTheDocument();
    expect(screen.getByText(/menor de edad, usa esta cuenta con un adulto responsable/i)).toBeInTheDocument();
    expect(screen.getByText(/ocultamos nombres, cédulas, teléfonos, correos y direcciones/i)).toBeInTheDocument();
    expect(screen.getByText(/este ocultamiento no es perfecto/i)).toBeInTheDocument();
    expect(screen.getByText(/eliminar tu cuenta/i)).toBeInTheDocument();
    expect(screen.getByText(/llama al 123/i)).toBeInTheDocument();
    expect(screen.getByText("Versión 2026-11-v4")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /entiendo y acepto/i }));
    expect(alAceptar).toHaveBeenCalledTimes(1);
  });

  it("muestra el error si no se pudo registrar la aceptación", () => {
    render(<Consentimiento version="v1" aceptando={false} error="No se pudo guardar" alAceptar={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo guardar");
  });
});

describe("avisos de salud", () => {
  it("el aviso permanente dice que no sustituye a un profesional y da el 123", () => {
    render(<AvisoSalud />);
    expect(screen.getByText(/no sustituye a un profesional de la salud/i)).toBeInTheDocument();
    expect(screen.getByText(/llama al 123/i)).toBeInTheDocument();
  });

  it("el aviso de urgencia es una alerta con el mensaje del agente", () => {
    render(<AvisoUrgencia mensaje="Llama ahora al 123 o acude a urgencias." />);
    expect(screen.getByRole("alert")).toHaveTextContent("Llama ahora al 123 o acude a urgencias.");
  });
});
