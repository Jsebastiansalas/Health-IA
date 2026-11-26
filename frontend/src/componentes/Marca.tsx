import { cn } from "../lib/cn";

/**
 * Logotipo: un cuadrado azul marino con la «M» y, debajo, el trazo de resaltador con el que se marca una cita.
 * El marino y la «M» son fijos; el trazo toma el color de cita del tema.
 */
export function Logotipo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-8", className)} fill="none" aria-hidden>
      <rect width="32" height="32" rx="8" fill="#0b2e4a" />
      <rect x="7" y="22" width="18" height="4" rx="2" className="fill-cita" />
      <path d="M8.5 20V9.5l5.75 7.25L20 9.5V20" stroke="#ffffff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M20 9.5h3.5V20" stroke="#ffffff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" opacity="0" />
    </svg>
  );
}

export function Marca({ className, compacta = false }: { className?: string; compacta?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-texto", className)}>
      <Logotipo />
      {!compacta && <span className="text-xl font-semibold leading-none tracking-tight">MedTender</span>}
    </span>
  );
}
