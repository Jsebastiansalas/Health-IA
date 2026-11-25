import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const llamadas = vi.hoisted(() => ({ post: [] as [string, unknown][], respuestas: {} as Record<string, unknown> }));

vi.mock("../api/cliente", () => ({
  api: async (ruta: string) => (ruta === "/auth/2fa" ? { activo: false, respaldos_disponibles: 0 } : {}),
  post: async (ruta: string, cuerpo: unknown) => {
    llamadas.post.push([ruta, cuerpo]);
    const r = llamadas.respuestas[ruta];
    if (r instanceof Error) throw r;
    return r ?? {};
  },
  guardarTokens: vi.fn(),
  haySesion: () => false,
  refreshActual: () => null,
  EVENTO_SESION_EXPIRADA: "x",
  EVENTO_DOS_PASOS_REQUERIDO: "y",
}));
vi.mock("qrcode", () => ({ default: { toDataURL: async () => "data:image/png;base64,AAA" } }));

const { ProveedorSesion } = await import("../sesion");
const { PaginaIngreso } = await import("./Ingreso");
const { PaginaSeguridad } = await import("./Seguridad");
const { PaginaOlvideContrasena } = await import("./Contrasena");

const pintar = (ui: React.ReactElement) =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <ProveedorSesion>{ui}</ProveedorSesion>
      </MemoryRouter>
    </QueryClientProvider>,
  );

describe("cuentas seguras", () => {
  beforeEach(() => {
    llamadas.post.length = 0;
    llamadas.respuestas = {};
  });

  it("si la cuenta tiene dos pasos, el ingreso pide el código y lo verifica con el desafío", async () => {
    llamadas.respuestas["/auth/login"] = { requiere2fa: true, desafio: "d-123", access_token: null };
    llamadas.respuestas["/auth/2fa/verificar"] = { access_token: "a", refresh_token: "r" };
    pintar(<PaginaIngreso />);
    fireEvent.change(screen.getByLabelText("Correo electrónico"), { target: { value: "ana@correo.co" } });
    fireEvent.change(screen.getByLabelText("Contraseña"), { target: { value: "Clave-Segura-123" } });
    fireEvent.click(screen.getByRole("button", { name: "Ingresar" }));
    const campo = await screen.findByLabelText("Código de verificación");
    expect(screen.getByRole("heading", { name: "Verificación en dos pasos" })).toBeInTheDocument();
    fireEvent.change(campo, { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Verificar" }));
    await waitFor(() => expect(llamadas.post).toContainEqual(["/auth/2fa/verificar", { desafio: "d-123", codigo: "123456" }]));
  });

  it("ofrece recuperar la contraseña y responde igual exista o no la cuenta", async () => {
    pintar(<PaginaOlvideContrasena />);
    fireEvent.change(screen.getByLabelText("Correo electrónico"), { target: { value: " ana@correo.co " } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar enlace" }));
    expect(await screen.findByText(/Si hay una cuenta con ese correo/)).toBeInTheDocument();
    expect(llamadas.post).toContainEqual(["/auth/olvide-contrasena", { email: "ana@correo.co" }]);
  });

  it("activar dos pasos muestra el QR, pide el código y enseña los códigos de respaldo una vez", async () => {
    llamadas.respuestas["/auth/2fa/iniciar"] = { secreto: "JBSWY3DPEHPK3PXP", uri: "otpauth://totp/MedTender:ana" };
    llamadas.respuestas["/auth/2fa/activar"] = { codigos_respaldo: ["abcd-efgh", "jkmn-pqrs"] };
    pintar(<PaginaSeguridad />);
    fireEvent.click(await screen.findByRole("button", { name: "Activar verificación en dos pasos" }));
    expect(await screen.findByAltText("Código QR para tu app de autenticación")).toBeInTheDocument();
    expect(screen.getByText("JBSW Y3DP EHPK 3PXP")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Código de la app"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Activar" }));
    expect(await screen.findByText("abcd-efgh")).toBeInTheDocument();
    expect(screen.getByText(/No los volveremos a mostrar/)).toBeInTheDocument();
  });
});
