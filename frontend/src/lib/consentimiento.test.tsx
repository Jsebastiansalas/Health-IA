import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const falso = vi.hoisted(() => ({ lecturas: 0, post: [] as [string, unknown][] }));
vi.mock("../api/cliente", () => ({
  api: async () => {
    falso.lecturas += 1;
    const version = falso.lecturas === 1 ? "2026-11-v3" : "2026-11-v5";
    return { version, requerido: true, aceptado: false, tipo_cuenta: "PERSONAL", proveedor_ia: "gemini_api", respaldo_ia: "" };
  },
  post: async (ruta: string, cuerpo: unknown) => {
    falso.post.push([ruta, cuerpo]);
    throw new Error("El texto del consentimiento cambió");
  },
}));

const { useConsentimiento } = await import("./consentimiento");

function Prueba() {
  const c = useConsentimiento();
  return (
    <>
      <p>{c.estado?.version}</p>
      <button onClick={() => c.aceptar.mutate()}>aceptar</button>
    </>
  );
}

describe("aceptar el consentimiento", () => {
  it("envía la versión que se mostró y, si el servidor la rechaza, vuelve a leer el texto vigente", async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <Prueba />
      </QueryClientProvider>,
    );
    await screen.findByText("2026-11-v3");
    fireEvent.click(screen.getByRole("button", { name: "aceptar" }));
    await waitFor(() => expect(falso.post).toEqual([["/consentimiento", { version: "2026-11-v3" }]]));
    expect(await screen.findByText("2026-11-v5")).toBeInTheDocument();
  });
});
