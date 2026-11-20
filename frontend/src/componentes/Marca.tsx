import { cn } from "../lib/cn";

/**
 * Logotipo: un folio con la esquina doblada, una «M» a tinta y el resaltador pasado por debajo,
 * como queda una cita marcada a mano. El folio y la tinta toman el color del texto (sirven en los
 * dos temas); el resaltador es siempre amarillo.
 */
export function Logotipo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={cn("size-8", className)} fill="none" aria-hidden>
      <path d="M9 4h16l8 8v24H9z" className="fill-folio" stroke="currentColor" strokeWidth="2.4" strokeLinejoin="round" />
      <path d="M25 4v8h8" stroke="currentColor" strokeWidth="2.4" strokeLinejoin="round" />
      <rect x="13" y="24.5" width="16" height="6" rx="1" className="fill-marca" />
      <path d="M14 29V17.5l5 6.5 5-6.5V29" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Marca({ className, compacta = false }: { className?: string; compacta?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5 text-tinta", className)}>
      <Logotipo />
      {!compacta && <span className="font-display text-[1.3rem] font-semibold leading-none tracking-[-0.01em]">MedTender</span>}
    </span>
  );
}
