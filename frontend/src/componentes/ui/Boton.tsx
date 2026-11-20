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
          "bg-eosina text-white shadow-[0_12px_26px_-12px_rgb(217_48_111/0.75),inset_0_1px_0_rgb(255_255_255/0.28)] hover:bg-eosina-osc hover:shadow-[0_16px_32px_-12px_rgb(217_48_111/0.85),inset_0_1px_0_rgb(255_255_255/0.3)]",
        secundario:
          "border border-ink/18 bg-white text-ink shadow-[0_1px_0_rgb(255_255_255),0_8px_18px_-14px_rgb(36_31_120/0.5)] hover:border-hema/50 hover:bg-lila-50",
        fantasma: "text-tx-2 hover:bg-hema/8 hover:text-hema-osc",
        peligro: "border border-coral/35 bg-coral/8 text-coral hover:bg-coral/14",
      },
      tamano: {
        sm: "h-8 rounded-lg px-3 text-[0.8rem]",
        md: "h-10 rounded-xl px-4 text-sm",
        lg: "h-12 rounded-2xl px-6 text-[0.95rem]",
        icono: "size-10 rounded-xl",
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
