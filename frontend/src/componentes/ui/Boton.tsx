import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

/** Variantes de botón. Se exporta la función para reutilizarla en enlaces (`<Link className={boton(...)}>`). */
export const boton = cva(
  "relative inline-flex select-none items-center justify-center gap-2 whitespace-nowrap font-medium transition-[transform,background-color,box-shadow,border-color,color] duration-200 ease-[var(--ease-salida)] active:translate-y-px disabled:pointer-events-none disabled:opacity-45",
  {
    variants: {
      variante: {
        primario: "bg-accion text-accion-tx hover:bg-accion-osc",
        secundario: "border border-tinta/35 bg-folio text-tinta hover:border-tinta/60 hover:bg-folio-2",
        fantasma: "text-tinta-2 hover:bg-tinta/[0.07] hover:text-tinta",
        peligro: "border border-peligro/50 bg-folio text-peligro hover:bg-peligro/10",
      },
      tamano: {
        sm: "h-8 rounded-md px-4 text-[0.8rem] pointer-coarse:h-10",
        md: "h-10 rounded-md px-5 text-sm pointer-coarse:h-11",
        lg: "h-12 rounded-md px-7 text-base",
        icono: "size-10 rounded-md pointer-coarse:size-11",
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
