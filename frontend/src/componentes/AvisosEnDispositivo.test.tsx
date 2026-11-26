import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AVISO_PUSH } from "../lib/avisoPush";

const falso = vi.hoisted(() => ({
  estado: { disponible: true, clave_publica: "BAbc_-12", dispositivos: 0, por_correo: true },
  llamadas: [] as [string, string, unknown][],
}));

vi.mock("../api/cliente", () => ({
  api: async (ruta: string, opciones?: { method?: string; body?: string }) => {
    if (!opciones?.method) return { ...falso.estado };
    falso.llamadas.push([opciones.method, ruta, JSON.parse(opciones.body ?? "null")]);
    return undefined;
  },
}));

const { AvisosEnDispositivo } = await import("./AvisosEnDispositivo");
const { olvidarDispositivo } = await import("../lib/notificaciones");

const ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc";

function navegador(permiso: NotificationPermission, yaSuscrito = false) {
  const suscripcion = { endpoint: ENDPOINT, unsubscribe: vi.fn(async () => true) };
  let actual: typeof suscripcion | null = yaSuscrito ? suscripcion : null;
  const pushManager = {
    getSubscription: vi.fn(async () => actual),
    subscribe: vi.fn(async (_opciones: PushSubscriptionOptionsInit) => (actual = suscripcion)),
  };
  const pedir = vi.fn(async () => permiso);
  vi.stubGlobal("PushManager", function PushManager() {});
  vi.stubGlobal("Notification", { permission: "default", requestPermission: pedir });
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: { getRegistration: async () => ({ pushManager }), ready: Promise.resolve({ pushManager }) },
  });
  return { suscripcion, pushManager, pedir };
}

const pintar = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <AvisosEnDispositivo />
    </QueryClientProvider>,
  );

describe("avisos en este dispositivo", () => {
  beforeEach(() => {
    falso.estado = { disponible: true, clave_publica: "BAbc_-12", dispositivos: 0, por_correo: true };
    falso.llamadas.length = 0;
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    Reflect.deleteProperty(navigator, "serviceWorker");
  });

  it("el texto de la notificación es fijo y no dice nada de salud", () => {
    expect(`${AVISO_PUSH.titulo} ${AVISO_PUSH.cuerpo}`).toBe("MedTender Tienes un recordatorio. Ábrelo en la aplicación.");
  });

  it("solo pide permiso cuando la persona lo pulsa y registra el dispositivo", async () => {
    const { pushManager, pedir } = navegador("granted");
    pintar();
    const activar = await screen.findByRole("button", { name: "Activar avisos en este dispositivo" });
    expect(pedir).not.toHaveBeenCalled();
    fireEvent.click(activar);
    await waitFor(() => expect(falso.llamadas).toContainEqual(["POST", "/push/suscripciones", { endpoint: ENDPOINT }]));
    expect(pushManager.subscribe.mock.calls[0]![0].userVisibleOnly).toBe(true);
    expect(pushManager.subscribe.mock.calls[0]![0].applicationServerKey).toBeInstanceOf(Uint8Array);
  });

  it("si niega el permiso lo explica y no registra nada", async () => {
    navegador("denied");
    pintar();
    fireEvent.click(await screen.findByRole("button", { name: "Activar avisos en este dispositivo" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/no diste permiso/i);
    expect(falso.llamadas).toHaveLength(0);
  });

  it("ya activado deja desactivarlo y elegir si sigue el correo", async () => {
    const { suscripcion } = navegador("granted", true);
    falso.estado.dispositivos = 1;
    pintar();
    const correo = await screen.findByRole("checkbox", { name: /también por correo/i });
    expect(correo).toBeChecked();
    fireEvent.click(correo);
    await waitFor(() => expect(falso.llamadas).toContainEqual(["PUT", "/push/preferencia", { por_correo: false }]));
    fireEvent.click(screen.getByRole("button", { name: "Desactivar en este dispositivo" }));
    await waitFor(() => expect(falso.llamadas).toContainEqual(["DELETE", "/push/suscripciones", { endpoint: ENDPOINT }]));
    expect(suscripcion.unsubscribe).toHaveBeenCalled();
  });

  it("no aparece si el servidor no las tiene o el navegador no puede", async () => {
    falso.estado.disponible = false;
    navegador("granted");
    const { container, unmount } = pintar();
    await new Promise((r) => setTimeout(r, 20));
    expect(container).toBeEmptyDOMElement();
    unmount();
    vi.unstubAllGlobals();
    Reflect.deleteProperty(navigator, "serviceWorker");
    expect(pintar().container).toBeEmptyDOMElement();
  });

  it("al cerrar sesión el dispositivo deja de estar suscrito sin llamar a la API", async () => {
    const { suscripcion } = navegador("granted", true);
    await olvidarDispositivo();
    expect(suscripcion.unsubscribe).toHaveBeenCalled();
    expect(falso.llamadas).toHaveLength(0);
  });
});
