import { cn } from "../lib/cn";

/**
 * Logotipo: una placa radiográfica (esquina muesca, como la de las películas) con una «M»
 * y el punto ámbar del hallazgo marcado.
 */
export function Logotipo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={cn("size-9", className)} fill="none" aria-hidden>
      <path d="M7 3h22l8 8v26a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" fill="#e4f3f8" />
      <path d="M29 3v6a2 2 0 0 0 2 2h6" fill="#b9d3dc" />
      <path d="M11 30V16l6.5 8L24 16v14" stroke="#0a1322" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="30" cy="29" r="3.2" fill="#ffc247" stroke="#0a1322" strokeWidth="1.4" />
    </svg>
  );
}

export function Marca({ className, compacta = false }: { className?: string; compacta?: boolean; oscuro?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <Logotipo />
      {!compacta && (
        <span className="font-display text-[1.3rem] font-extrabold tracking-tight text-tx [font-stretch:90%]">
          Med<span className="font-medium text-hema">Tender</span>
        </span>
      )}
    </span>
  );
}
