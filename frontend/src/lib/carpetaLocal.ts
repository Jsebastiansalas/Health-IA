/**
 * Visor local desacoplado: acceso de solo lectura a la carpeta de PDFs del usuario con la
 * File System Access API. Los archivos se leen en memoria del navegador y NUNCA se suben.
 *
 * - El permiso se recuerda entre visitas guardando el handle en IndexedDB (el navegador
 *   vuelve a pedir confirmación con un clic).
 * - Primero se busca por nombre; si el archivo fue renombrado, se busca por SHA-256.
 */
import { mismoHash, sha256Hex } from "./sha256";

export const soportaCarpetas = () => typeof window !== "undefined" && "showDirectoryPicker" in window;

export interface PdfLocal {
  archivo: File;
  ruta: string;
}

const PROFUNDIDAD_MAXIMA = 4;

export async function* recorrerPdfs(
  dir: FileSystemDirectoryHandle,
  prefijo = "",
  profundidad = 0,
): AsyncGenerator<{ handle: FileSystemFileHandle; ruta: string }> {
  for await (const entrada of dir.values()) {
    const ruta = prefijo ? `${prefijo}/${entrada.name}` : entrada.name;
    if (entrada.kind === "file" && entrada.name.toLowerCase().endsWith(".pdf")) {
      yield { handle: entrada, ruta };
    } else if (entrada.kind === "directory" && profundidad < PROFUNDIDAD_MAXIMA) {
      yield* recorrerPdfs(entrada, ruta, profundidad + 1);
    }
  }
}

// Caché de hashes por sesión: (ruta, tamaño, fecha de modificación) -> SHA-256.
const cacheHashes = new Map<string, string>();

async function hashDe(archivo: File, ruta: string): Promise<string> {
  const clave = `${ruta}:${archivo.size}:${archivo.lastModified}`;
  let hash = cacheHashes.get(clave);
  if (!hash) {
    hash = await sha256Hex(await archivo.arrayBuffer());
    cacheHashes.set(clave, hash);
  }
  return hash;
}

export type ResultadoBusqueda =
  | { tipo: "coincide"; pdf: PdfLocal; porNombre: boolean }
  | { tipo: "distinto"; pdf: PdfLocal; hashLocal: string }
  | { tipo: "no-encontrado" };

export async function localizarOriginal(
  dir: FileSystemDirectoryHandle,
  nombre: string,
  sha256: string,
  alAvanzar?: (revisados: number) => void,
): Promise<ResultadoBusqueda> {
  const candidatos: { handle: FileSystemFileHandle; ruta: string }[] = [];
  let porNombre: PdfLocal | null = null;
  for await (const c of recorrerPdfs(dir)) {
    candidatos.push(c);
    if (!porNombre && c.handle.name === nombre) porNombre = { archivo: await c.handle.getFile(), ruta: c.ruta };
  }

  let distinto: ResultadoBusqueda | null = null;
  if (porNombre) {
    const hash = await hashDe(porNombre.archivo, porNombre.ruta);
    if (mismoHash(hash, sha256)) return { tipo: "coincide", pdf: porNombre, porNombre: true };
    distinto = { tipo: "distinto", pdf: porNombre, hashLocal: hash };
  }

  // Quizá el original fue renombrado: se compara por contenido.
  let revisados = 0;
  for (const c of candidatos) {
    if (c.ruta === porNombre?.ruta) continue;
    const archivo = await c.handle.getFile();
    alAvanzar?.(++revisados);
    if (mismoHash(await hashDe(archivo, c.ruta), sha256)) {
      return { tipo: "coincide", pdf: { archivo, ruta: c.ruta }, porNombre: false };
    }
  }
  return distinto ?? { tipo: "no-encontrado" };
}

// ---------- Persistencia del handle (IndexedDB) ----------
const DB = "medtender-visor";
const STORE = "carpetas";

function abrir(): Promise<IDBDatabase> {
  return new Promise((ok, error) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => ok(req.result);
    req.onerror = () => error(req.error);
  });
}

export async function recordarCarpeta(handle: FileSystemDirectoryHandle | null): Promise<void> {
  const db = await abrir();
  await new Promise<void>((ok, error) => {
    const tx = db.transaction(STORE, "readwrite");
    if (handle) tx.objectStore(STORE).put(handle, "pdfs");
    else tx.objectStore(STORE).delete("pdfs");
    tx.oncomplete = () => ok();
    tx.onerror = () => error(tx.error);
  });
}

export async function carpetaRecordada(): Promise<FileSystemDirectoryHandle | null> {
  try {
    const db = await abrir();
    return await new Promise((ok) => {
      const req = db.transaction(STORE).objectStore(STORE).get("pdfs");
      req.onsuccess = () => ok((req.result as FileSystemDirectoryHandle) ?? null);
      req.onerror = () => ok(null);
    });
  } catch {
    return null;
  }
}

export async function tienePermiso(handle: FileSystemDirectoryHandle, pedir = false): Promise<boolean> {
  const opciones = { mode: "read" as const };
  if ((await handle.queryPermission(opciones)) === "granted") return true;
  return pedir && (await handle.requestPermission(opciones)) === "granted";
}

export async function elegirCarpeta(): Promise<FileSystemDirectoryHandle> {
  const handle = await window.showDirectoryPicker({ id: "medtender-pdfs", mode: "read" });
  await recordarCarpeta(handle);
  return handle;
}
