import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

/** Etiqueta de estado: pequeña, de borde completo y un solo color por significado. */
const insignia = cva(
  "inline-flex items-center gap-1 rounded-lg border px-2 py-0.5 text-xs font-medium",
  {
    variants: {
      tono: {
        neutro: "border-borde bg-panel-2 text-texto-2",
        accion: "border-primario/35 bg-primario/10 text-primario",
        marca: "border-cita-borde bg-cita text-cita-tx",
        ok: "border-ok/35 bg-ok/10 text-ok",
        aviso: "border-aviso/40 bg-aviso/10 text-aviso",
        peligro: "border-peligro/40 bg-peligro/10 text-peligro",
      },
    },
    defaultVariants: { tono: "neutro" },
  },
);

export function Insignia({
  tono,
  className,
  ...resto
}: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof insignia>) {
  return <span className={cn(insignia({ tono }), className)} {...resto} />;
}
