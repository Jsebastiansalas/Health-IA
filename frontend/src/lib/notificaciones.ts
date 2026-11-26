/** Suscripción del navegador a las notificaciones push. */

export const compatibles = () =>
  typeof navigator !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

/** La clave VAPID llega en base64url; el navegador la pide en bytes. */
export function aBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const base64 = (base64url + "=".repeat((4 - (base64url.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  const crudo = atob(base64);
  const bytes = new Uint8Array(crudo.length);
  for (let i = 0; i < crudo.length; i++) bytes[i] = crudo.charCodeAt(i);
  return bytes;
}

export async function suscripcionActual(): Promise<PushSubscription | null> {
  if (!compatibles()) return null;
  const registro = await navigator.serviceWorker.getRegistration();
  return (await registro?.pushManager.getSubscription()) ?? null;
}

/** Pide permiso (solo tras un clic de la persona) y suscribe este dispositivo. */
export async function suscribir(clavePublica: string): Promise<PushSubscription> {
  if ((await Notification.requestPermission()) !== "granted") {
    throw new Error("No diste permiso para las notificaciones. Puedes cambiarlo en los ajustes del navegador.");
  }
  const registro = await navigator.serviceWorker.ready;
  return registro.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: aBytes(clavePublica) });
}

/**
 * Al cerrar sesión: se cancela en el navegador, sin llamar a la API (la sesión ya puede no valer). El
 * servidor borra la suscripción cuando el servicio de push le responde que ya no existe.
 */
export async function olvidarDispositivo(): Promise<void> {
  try {
    await (await suscripcionActual())?.unsubscribe();
  } catch {
    // Cerrar la sesión no puede fallar por esto.
  }
}
