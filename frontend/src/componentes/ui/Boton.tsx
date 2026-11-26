import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/cn";
import { Loader2 } from "../../iconos";

/** Variantes de botón. Se exporta la función para reutilizarla en enlaces (`<Link className={boton(...)}>`). */
export const boton = cva(
  "relative inline-flex select-none items-center justify-center gap-2 whitespace-nowrap font-semibold transition-[transform,background-color,border-color,color,opacity] duration-300 ease-[var(--ease-salida)] active:scale-[0.98] disabled:pointer-events-none disabled:opacity-45",
  {
    variants: {
      variante: {
        primario: "bg-primario text-primario-tx hover:bg-primario-osc",
        secundario: "border border-borde bg-panel text-texto hover:bg-panel-2",
        fantasma: "text-texto-2 hover:bg-panel-2 hover:text-texto",
        peligro: "border border-peligro/40 bg-panel text-peligro hover:bg-peligro/10",
      },
      tamano: {
        sm: "h-8 rounded-lg px-3 text-sm pointer-coarse:h-10",
        md: "h-10 rounded-lg px-3 text-base pointer-coarse:h-11",
        lg: "h-12 rounded-lg px-4 text-lg",
        icono: "size-10 rounded-lg pointer-coarse:size-11",
      },
    },
    defaultVariants: { variante: "secundario", tamano: "md" },
  },
);

type Props = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof boton> & { cargando?: boolean };

export function Boton({ variante, tamano, cargando, className, children, disabled, ...resto }: Props) {
  return (
    <button
      className={cn(boton({ variante, tamano }), className)}
      disabled={disabled || cargando}
      aria-busy={cargando || undefined}
      {...resto}
    >
      {cargando && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}
