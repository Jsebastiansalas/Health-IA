import { cn } from "../lib/cn";

/** Una célula dibujada: membrana, citoplasma rosa y núcleo índigo con cromatina. */
export function Celula({
  className,
  tono = "eosina",
  rotacion = 0,
}: {
  className?: string;
  tono?: "eosina" | "lavanda";
  rotacion?: number;
}) {
  const cito = tono === "eosina" ? "#f6b7d2" : "#cbc2f4";
  const membrana = tono === "eosina" ? "#c4447f" : "#6f63d8";
  return (
    <svg viewBox="0 0 100 100" className={className} style={{ transform: `rotate(${rotacion}deg)` }} aria-hidden>
      <path
        d="M50 5c19 0 38 12 43 32 4 17-3 38-20 50-15 10-39 11-54-2C5 70 3 47 11 31 19 15 34 5 50 5Z"
        fill={cito}
        stroke={membrana}
        strokeWidth="2.5"
      />
      <ellipse cx="48" cy="50" rx="21" ry="17" fill="#4b3fc9" transform="rotate(-18 48 50)" />
      <ellipse cx="42" cy="44" rx="9" ry="6" fill="#7468df" opacity="0.7" transform="rotate(-18 42 44)" />
      <circle cx="54" cy="55" r="3" fill="#1c1752" opacity="0.6" />
      <circle cx="46" cy="58" r="2" fill="#1c1752" opacity="0.5" />
      <circle cx="39" cy="50" r="1.6" fill="#fff" opacity="0.35" />
    </svg>
  );
}

/** Racimo de células: decoración de tarjetas y estados vacíos. */
export function Molecula({ className }: { className?: string }) {
  return (
    <div className={cn("relative aspect-[3/2]", className)} aria-hidden>
      <Celula className="absolute left-[2%] top-[22%] w-[38%]" rotacion={-12} />
      <Celula className="absolute left-[34%] top-0 w-[34%]" tono="lavanda" rotacion={20} />
      <Celula className="absolute left-[58%] top-[30%] w-[40%]" rotacion={8} />
      <Celula className="absolute left-[24%] top-[52%] w-[30%]" tono="lavanda" rotacion={-30} />
    </div>
  );
}

/** Barra de escala de micrografía: «50 µm» sobre una regla con topes. */
export function BarraEscala({ micras = 50, className }: { micras?: number; className?: string }) {
  return (
    <div className={cn("inline-flex flex-col items-start gap-1 font-mono text-[0.7rem] font-semibold text-ink", className)} aria-hidden>
      <span>{micras} µm</span>
      <svg width="84" height="8" viewBox="0 0 84 8" fill="none">
        <path d="M1 1v6M83 1v6M1 4h82" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    </div>
  );
}

/** Fibra de colágeno: divisor ondulado entre secciones. */
export function Fibra({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 1200 40" preserveAspectRatio="none" className={cn("h-8 w-full", className)} fill="none" aria-hidden>
      <path d="M0 22c60-18 110 14 180 0s120-18 190-2 130 16 200 0 120-18 190-2 130 16 200 2 120-16 240 0" stroke="#d9306f" strokeOpacity="0.45" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M0 26c70-14 100 12 170 0s130-14 200 0 120 14 190 0 130-14 200 0 120 12 240-2" stroke="#4b3fc9" strokeOpacity="0.3" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

/** Escudo con candado dibujado como una lámina de estudio: la promesa de que el PDF no se queda. */
export function Escudo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 160 180" className={className} fill="none" aria-hidden>
      <path d="M80 14 136 36v48c0 38-24 62-56 78-32-16-56-40-56-78V36L80 14Z" fill="#f7c1d6" stroke="#1c1752" strokeWidth="2.5" />
      <path d="M80 30 122 46v38c0 28-17 47-42 61-25-14-42-33-42-61V46L80 30Z" fill="#fff" stroke="#d9306f" strokeWidth="1.5" strokeDasharray="3 5" />
      <rect x="60" y="80" width="40" height="34" rx="7" fill="#4b3fc9" stroke="#1c1752" strokeWidth="2.5" />
      <path d="M68 80V70a12 12 0 0 1 24 0v10" stroke="#1c1752" strokeWidth="3" strokeLinecap="round" />
      <circle cx="80" cy="95" r="4.5" fill="#f7c1d6" />
      <path d="M80 99v7" stroke="#f7c1d6" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
