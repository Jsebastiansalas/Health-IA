import { del, get } from "idb-keyval";
import { useCallback, useEffect, useState } from "react";
import { CLAVE_COMPARTIDO } from "./claveCompartido";

const EVENTO = "medtender:compartido-cambio";

/** El archivo que llegó desde «Compartir» y aún no se ha subido ni descartado. */
export async function leerCompartido(): Promise<File | null> {
  try {
    const v = await get<File>(CLAVE_COMPARTIDO);
    return v instanceof Blob ? (v as File) : null;
  } catch {
    return null;
  }
}

/** Borra el archivo del teléfono: se llama al subirlo y al cancelar. */
export async function descartarCompartido(): Promise<void> {
  try {
    await del(CLAVE_COMPARTIDO);
  } finally {
    window.dispatchEvent(new Event(EVENTO));
  }
}

/** Archivo compartido pendiente (o null), y cómo refrescarlo. */
export function useCompartido() {
  const [archivo, setArchivo] = useState<File | null>(null);
  const [cargando, setCargando] = useState(true);
  const leer = useCallback(() => {
    void leerCompartido().then((a) => {
      setArchivo(a);
      setCargando(false);
    });
  }, []);
  useEffect(() => {
    leer();
    window.addEventListener(EVENTO, leer);
    return () => window.removeEventListener(EVENTO, leer);
  }, [leer]);
  return { archivo, cargando };
}
