import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

/** Sello de estado: rótulo rectangular de borde fino, como los que se estampan en un folio. */
const insignia = cva(
  "inline-flex items-center gap-1.5 rounded-[3px] border px-2 py-0.5 text-[0.72rem] font-medium leading-5",
  {
    variants: {
      tono: {
        neutro: "border-tinta/20 bg-tinta/[0.04] text-tinta-2",
        accion: "border-accion/40 bg-accion/10 text-accion",
        marca: "border-transparent bg-marca text-marca-tx",
        ok: "border-ok/40 bg-ok/10 text-ok",
        aviso: "border-aviso/45 bg-aviso/10 text-aviso",
        peligro: "border-peligro/45 bg-peligro/10 text-peligro",
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
