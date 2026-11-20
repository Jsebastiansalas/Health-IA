import { cn } from "../lib/cn";

/** Logotipo: dos círculos concéntricos (la lente de lectura) con una «M» de trazo fino en el centro. */
export function Logotipo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={cn("size-8", className)} fill="none" aria-hidden>
      <circle cx="20" cy="20" r="18" stroke="#ededf3" strokeWidth="1.6" />
      <circle cx="20" cy="20" r="12.5" stroke="#ededf3" strokeOpacity="0.45" strokeWidth="1.2" />
      <path d="M13.5 25V15.5l6.5 6.5 6.5-6.5V25" stroke="#ededf3" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Marca({ className, compacta = false }: { className?: string; compacta?: boolean; oscuro?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <Logotipo />
      {!compacta && <span className="font-display text-[1.2rem] font-[480] tracking-[0.02em] text-tx [font-stretch:115%]">MedTender</span>}
    </span>
  );
}
