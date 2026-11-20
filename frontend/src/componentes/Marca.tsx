import { cn } from "../lib/cn";

/** Logotipo: una célula (núcleo índigo en citoplasma rosa) con un pulso que forma una «M». */
export function Logotipo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={cn("size-9", className)} fill="none" aria-hidden>
      <path d="M20 3c9 0 17 6 17 16 0 9-6 18-17 18S3 29 3 20C3 10 11 3 20 3Z" fill="#f7a8c8" stroke="#1c1752" strokeWidth="2" />
      <ellipse cx="20" cy="20" rx="11" ry="9" fill="#4b3fc9" transform="rotate(-14 20 20)" />
      <path d="M12.5 24 16 15.5 20 22.5 24 15.5 27.5 24" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Marca({ className, compacta = false, oscuro = false }: { className?: string; compacta?: boolean; oscuro?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <Logotipo />
      {!compacta && (
        <span className={cn("font-display text-[1.35rem] font-bold tracking-tight", oscuro ? "text-white" : "text-ink")}>
          Med<span className={oscuro ? "text-eosina-clara" : "text-eosina"}>Tender</span>
        </span>
      )}
    </span>
  );
}
