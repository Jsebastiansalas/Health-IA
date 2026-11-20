import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

/** Variantes de botón. Se exporta la función para reutilizarla en enlaces (`<Link className={boton(...)}>`). */
export const boton = cva(
  "relative inline-flex select-none items-center justify-center gap-2 whitespace-nowrap font-semibold transition-[transform,background-color,box-shadow,border-color,color] duration-200 ease-[var(--ease-salida)] active:translate-y-px disabled:pointer-events-none disabled:opacity-45",
  {
    variants: {
      variante: {
        primario:
          "bg-luz text-[#07101c] shadow-[0_10px_18px_-10px_rgb(0_0_0/0.9),inset_0_-2px_0_rgb(91_131_146/0.45)] hover:bg-white",
        secundario:
          "border border-ink/25 bg-transparent text-tx hover:border-hema/70 hover:bg-ink/[0.06]",
        fantasma: "text-tx-2 hover:bg-ink/[0.07] hover:text-tx",
        peligro: "border border-coral/40 bg-coral/10 text-coral hover:bg-coral/20",
      },
      tamano: {
        sm: "h-8 rounded-md px-3 text-[0.8rem]",
        md: "h-10 rounded-lg px-4 text-sm",
        lg: "h-12 rounded-xl px-6 text-[0.95rem]",
        icono: "size-10 rounded-lg",
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
