import { registerSW } from "virtual:pwa-register";
import { EVENTO_VERSION_NUEVA } from "./componentes/AvisosApp";

let actualizar: ((recargar?: boolean) => Promise<void>) | null = null;

/** Registra el service worker (solo en producción) y avisa cuando hay una versión nueva lista. */
export function registrarApp(): void {
  if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return;
  actualizar = registerSW({
    onNeedRefresh: () => window.dispatchEvent(new Event(EVENTO_VERSION_NUEVA)),
  });
}

/** Activa la versión nueva y recarga la página. */
export function aplicarVersionNueva(): void {
  if (actualizar) void actualizar(true);
  else window.location.reload();
}
