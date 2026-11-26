import type { ProveedorIa } from "../lib/proveedorIa";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AvisoSalud, AvisoUrgencia } from "./AvisoSalud";
import { Consentimiento } from "./Consentimiento";

describe("Consentimiento", () => {
  it("explica qué se envía, a quién y cómo borrar, y deja aceptar", () => {
    const alAceptar = vi.fn();
    render(<Consentimiento version="2026-11-v5-claude" ia={{ proveedor: "vertex", respaldo: "claude" }} aceptando={false} alAceptar={alAceptar} />);
    expect(screen.getByRole("heading", { name: /antes de usar tus documentos de salud/i })).toBeInTheDocument();
    expect(screen.getByText(/pruebas cerradas: puede equivocarse/i)).toBeInTheDocument();
    expect(screen.getByText(/copias de seguridad conservan los datos hasta 14 días más/i)).toBeInTheDocument();
    expect(screen.getByText(/sin fecha de vencimiento/i)).toBeInTheDocument();
    expect(screen.getByText(/documentos de otra persona, declaras que tienes derecho/i)).toBeInTheDocument();
    expect(screen.getByText(/menor de edad, usa esta cuenta con un adulto responsable/i)).toBeInTheDocument();
    expect(screen.getByText(/ocultamos nombres, cédulas, teléfonos, correos y direcciones/i)).toBeInTheDocument();
    expect(screen.getByText(/este ocultamiento no es perfecto/i)).toBeInTheDocument();
    expect(screen.getByText(/eliminar tu cuenta/i)).toBeInTheDocument();
    expect(screen.getByText(/llama al 123/i)).toBeInTheDocument();
    expect(screen.getByText("Versión 2026-11-v5-claude")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /entiendo y acepto/i }));
    expect(alAceptar).toHaveBeenCalledTimes(1);
  });

  it("muestra el error si no se pudo registrar la aceptación", () => {
    render(<Consentimiento version="v1" ia={{ proveedor: "gemini_api", respaldo: "" }} aceptando={false} error="No se pudo guardar" alAceptar={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo guardar");
  });
});

describe("el consentimiento dice la verdad sobre el proveedor activo", () => {
  const textoCon = (ia: ProveedorIa) => {
    const { container, unmount } = render(<Consentimiento version="v" ia={ia} aceptando={false} alAceptar={() => {}} />);
    const texto = container.textContent ?? "";
    unmount();
    return texto;
  };

  it("con la API gratuita avisa que Google puede usar lo que recibe y no promete lo contrario", () => {
    const t = textoCon({ proveedor: "gemini_api", respaldo: "" });
    expect(t).toMatch(/versión gratuita, y Google puede conservar y usar lo que se le envía/);
    expect(t).not.toMatch(/Vertex|Claude|no usa lo que le enviamos/);
  });

  it("con la API gratuita y Claude de respaldo nombra a las dos empresas sin extender la promesa a Google", () => {
    const t = textoCon({ proveedor: "gemini_api", respaldo: "claude" });
    expect(t).toMatch(/Google puede conservar y usar lo que se le envía/);
    expect(t).toMatch(/Claude, de Anthropic, otra empresa que no usa lo que le enviamos para entrenar/);
    expect(t).not.toMatch(/Vertex|Ninguno de los dos/);
  });

  it("con Vertex sin respaldo no menciona a Claude ni la versión gratuita", () => {
    const t = textoCon({ proveedor: "vertex", respaldo: "" });
    expect(t).toMatch(/Gemini en Google Cloud \(Vertex AI\)/);
    expect(t).toMatch(/Google no usa lo que le enviamos para entrenar sus modelos/);
    expect(t).not.toMatch(/Claude|gratuita/);
  });

  it("con Vertex y Claude de respaldo nombra a los dos", () => {
    const t = textoCon({ proveedor: "vertex", respaldo: "claude" });
    expect(t).toMatch(/Vertex AI\) y, solo si ese servicio falla, Claude de Anthropic/);
    expect(t).toMatch(/Ninguno de los dos usa lo que les enviamos para entrenar sus modelos/);
    expect(t).not.toMatch(/gratuita/);
  });

  it("nunca afirma que ya hay un contrato firmado", () => {
    for (const proveedor of ["gemini_api", "vertex"] as const)
      for (const respaldo of ["", "claude"] as const) expect(textoCon({ proveedor, respaldo })).not.toMatch(/contrato/i);
  });

  it("si no se sabe qué proveedor está activo, no deja aceptar", () => {
    render(<Consentimiento version="" ia={null} aceptando={false} alAceptar={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/No pudimos comprobar/);
    expect(screen.queryByRole("button", { name: /entiendo y acepto/i })).not.toBeInTheDocument();
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
