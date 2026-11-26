import { useEffect, useState } from "react";
import { ArrowsClockwise, WifiSlash } from "../iconos";
import { Boton } from "./ui/Boton";

/** Nombre del evento que dispara el registro del service worker cuando hay una versión nueva. */
export const EVENTO_VERSION_NUEVA = "medtender:version-nueva";

/**
 * Avisos propios de la app instalada: sin conexión y versión nueva disponible.
 * Fijos abajo, sin tapar el contenido, y anunciados a los lectores de pantalla.
 */
export function AvisosApp({ alActualizar }: { alActualizar: () => void }) {
  const [enLinea, setEnLinea] = useState(() => (typeof navigator === "undefined" ? true : navigator.onLine));
  const [versionNueva, setVersionNueva] = useState(false);

  useEffect(() => {
    const conectar = () => setEnLinea(true);
    const desconectar = () => setEnLinea(false);
    const nueva = () => setVersionNueva(true);
    window.addEventListener("online", conectar);
    window.addEventListener("offline", desconectar);
    window.addEventListener(EVENTO_VERSION_NUEVA, nueva);
    return () => {
      window.removeEventListener("online", conectar);
      window.removeEventListener("offline", desconectar);
      window.removeEventListener(EVENTO_VERSION_NUEVA, nueva);
    };
  }, []);

  if (enLinea && !versionNueva) return null;
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[90] flex flex-col items-center gap-2 px-4">
      {!enLinea && (
        <p role="status" className="panel pointer-events-auto flex max-w-md items-start gap-3 px-4 py-3 text-sm shadow-lg">
          <WifiSlash className="mt-0.5 size-4 shrink-0 text-aviso" aria-hidden />
          <span>Sin conexión. Puedes moverte por la app, pero para consultar o subir documentos hace falta internet.</span>
        </p>
      )}
      {versionNueva && (
        <div role="status" className="panel pointer-events-auto flex max-w-md items-center gap-3 px-4 py-3 text-sm shadow-lg">
          <ArrowsClockwise className="size-4 shrink-0 text-primario" aria-hidden />
          <span className="flex-1">Hay una versión nueva de MedTender.</span>
          <Boton tamano="sm" variante="primario" onClick={alActualizar}>
            Actualizar
          </Boton>
        </div>
      )}
    </div>
  );
}
