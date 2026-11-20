import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

/** Variantes de botón. Se exporta la función para reutilizarla en enlaces (`<Link className={boton(...)}>`). */
export const boton = cva(
  "relative inline-flex select-none items-center justify-center gap-2 whitespace-nowrap font-normal transition-[transform,background-color,box-shadow,border-color,color] duration-200 ease-[var(--ease-salida)] active:translate-y-px disabled:pointer-events-none disabled:opacity-45",
  {
    variants: {
      variante: {
        primario: "bg-cobalto text-white hover:bg-cobalto-osc",
        secundario: "border border-ink/80 bg-transparent text-tx hover:bg-ink/10",
        fantasma: "text-tx-2 hover:bg-ink/[0.08] hover:text-tx",
        peligro: "border border-coral/50 bg-coral/10 text-coral hover:bg-coral/20",
      },
      tamano: {
        sm: "h-8 rounded-full px-4 text-[0.8rem]",
        md: "h-10 rounded-full px-5 text-sm",
        lg: "h-12 rounded-full px-7 text-base",
        icono: "size-10 rounded-full",
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
