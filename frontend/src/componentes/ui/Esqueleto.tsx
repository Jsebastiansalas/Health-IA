import type { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

/** Marcador de carga con brillo. Decorativo: el contenedor debe llevar `aria-busy`. */
export function Esqueleto({ className, ...resto }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("esqueleto", className)} aria-hidden {...resto} />;
}
