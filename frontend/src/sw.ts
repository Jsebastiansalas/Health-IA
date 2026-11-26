/*
 * Service worker de MedTender (vite-plugin-pwa, estrategia injectManifest).
 *
 * Qué guarda en el teléfono: SOLO el armazón de la aplicación (HTML, JS, CSS, fuentes e iconos), para que abra
 * rápido e instalada. NUNCA guarda respuestas de /api, documentos ni datos de salud: no hay ninguna ruta de
 * caché para ellos, así que siempre van a la red.
 *
 * «Compartir» (share_target): Android y escritorio envían aquí, por POST multipart, la foto o el PDF que el
 * usuario compartió desde otra app. Se guarda un momento en IndexedDB y se abre /compartir para elegir el
 * expediente; esa página lo borra al subirlo o al cancelar.
 */
import { set } from "idb-keyval";
import { AVISO_PUSH } from "./lib/avisoPush";
import { CLAVE_COMPARTIDO } from "./lib/claveCompartido";
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";

type EventoFetch = Event & { request: Request; respondWith(r: Promise<Response> | Response): void };
type EventoMensaje = Event & { data?: { type?: string } };
const sw = self as unknown as {
  skipWaiting(): Promise<void>;
  addEventListener(tipo: "fetch", f: (e: EventoFetch) => void): void;
  addEventListener(tipo: "message", f: (e: EventoMensaje) => void): void;
};

// Primero el receptor de «Compartir»: es un POST, ninguna ruta de Workbox lo atiende.
sw.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "POST" || url.pathname !== "/compartir") return;
  e.respondWith(
    (async () => {
      try {
        const datos = await e.request.formData();
        const archivo = datos.getAll("archivo").find((v): v is File => v instanceof File);
        if (archivo) await set(CLAVE_COMPARTIDO, archivo);
      } catch {
        /* si falla, /compartir dirá que no llegó ningún archivo */
      }
      return Response.redirect("/compartir", 303);
    })(),
  );
});

cleanupOutdatedCaches();
// Workbox sustituye `self.__WB_MANIFEST` (texto literal) por la lista del armazón al compilar.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
precacheAndRoute((self as any).__WB_MANIFEST);

// Aplicación de una sola página: toda navegación abre index.html desde la caché, salvo la API y los videos.
registerRoute(new NavigationRoute(createHandlerBoundToURL("/index.html"), { denylist: [/^\/api\//, /^\/recorrido\//] }));

// La página pide activar la versión nueva cuando el usuario pulsa «Actualizar».
sw.addEventListener("message", (e) => {
  if (e.data?.type === "SKIP_WAITING") void sw.skipWaiting();
});

// ---------- Notificaciones de recordatorios ----------
// Llegan sin contenido: el texto es fijo (lib/avisoPush.ts).
type EventoPush = Event & { waitUntil(p: Promise<unknown>): void };
type EventoClic = EventoPush & { notification: { close(): void } };
type Ventana = { url: string; focus(): Promise<unknown>; navigate?(url: string): Promise<unknown> };
const notificador = self as unknown as {
  registration: { showNotification(titulo: string, opciones: NotificationOptions): Promise<void> };
  clients: { matchAll(o: { type: "window" }): Promise<Ventana[]>; openWindow(url: string): Promise<unknown> };
  addEventListener(tipo: "push", f: (e: EventoPush) => void): void;
  addEventListener(tipo: "notificationclick", f: (e: EventoClic) => void): void;
};

notificador.addEventListener("push", (e) => {
  e.waitUntil(
    notificador.registration.showNotification(AVISO_PUSH.titulo, {
      body: AVISO_PUSH.cuerpo,
      tag: AVISO_PUSH.etiqueta,
      icon: "/icono-192.png",
    }),
  );
});

notificador.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil(
    (async () => {
      const [abierta] = await notificador.clients.matchAll({ type: "window" });
      if (!abierta) return notificador.clients.openWindow(AVISO_PUSH.destino);
      await abierta.navigate?.(AVISO_PUSH.destino);
      return abierta.focus();
    })(),
  );
});
