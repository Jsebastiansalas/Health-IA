import { useEffect, useState } from "react";

/** ¿El usuario pidió menos movimiento? Se actualiza si cambia la preferencia. */
export function useMovimientoReducido(): boolean {
  const [reducido, setReducido] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    const consulta = window.matchMedia("(prefers-reduced-motion: reduce)");
    const alCambiar = () => setReducido(consulta.matches);
    consulta.addEventListener("change", alCambiar);
    return () => consulta.removeEventListener("change", alCambiar);
  }, []);
  return reducido;
}
