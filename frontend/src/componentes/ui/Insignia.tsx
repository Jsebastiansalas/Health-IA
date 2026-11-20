import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

const insignia = cva(
  "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-0.5 text-[0.72rem] font-semibold leading-5",
  {
    variants: {
      tono: {
        neutro: "border-ink/15 bg-ink/[0.05] text-tx-2",
        hema: "border-hema/30 bg-hema/10 text-hema",
        eosina: "border-eosina/35 bg-eosina/10 text-eosina",
        ok: "border-ok/30 bg-ok/10 text-ok",
        ambar: "border-ambar/35 bg-ambar/10 text-ambar",
        coral: "border-coral/35 bg-coral/8 text-coral",
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
