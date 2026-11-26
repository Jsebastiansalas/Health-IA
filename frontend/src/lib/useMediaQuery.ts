import { useSyncExternalStore } from "react";

/** `true` mientras la consulta de medios se cumple; se actualiza al redimensionar la ventana. */
export function useMediaQuery(consulta: string): boolean {
  return useSyncExternalStore(
    (aviso) => {
      const mq = window.matchMedia(consulta);
      mq.addEventListener("change", aviso);
      return () => mq.removeEventListener("change", aviso);
    },
    () => window.matchMedia(consulta).matches,
    () => false,
  );
}
