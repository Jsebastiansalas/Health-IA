import { useId, type ReactNode } from "react";
import { cn } from "../lib/cn";

/* Piezas del negatoscopio: el panel de luz, la placa (la hoja del pliego como radiografía),
   las pinzas, las perforaciones de película y el trazo de rotulador de cera. Todo dibujado en código. */

const W = 410;
const H = 500;

/** Una línea de texto de la hoja vista como radiografía: densidad (opacidad) y largo variables. */
type Linea = { y: number; x?: number; w: number; o: number };

const LINEAS: Linea[] = [
  // párrafo de apertura
  { y: 116, w: 322, o: 0.5 },
  { y: 127, w: 336, o: 0.42 },
  { y: 138, w: 300, o: 0.5 },
  { y: 149, w: 330, o: 0.38 },
  { y: 160, w: 214, o: 0.46 },
  // cláusula citada (más densa: es el hallazgo)
  { y: 226, w: 330, o: 0.92 },
  { y: 238, w: 318, o: 0.88 },
  { y: 250, w: 262, o: 0.9 },
  // resto
  { y: 282, w: 334, o: 0.42 },
  { y: 293, w: 316, o: 0.5 },
  { y: 304, w: 336, o: 0.4 },
  { y: 315, w: 290, o: 0.48 },
  { y: 326, w: 188, o: 0.4 },
];

/** Agrupación de líneas en fragmentos (paso «lo indexamos y lo borramos»). */
const FRAGMENTOS: { n: string; y: number; h: number }[] = [
  { n: "F-01", y: 108, h: 62 },
  { n: "F-02", y: 216, h: 46 },
  { n: "F-03", y: 274, h: 64 },
  { n: "F-04", y: 350, h: 76 },
];

export type ModoPlaca = "completo" | "escaneo" | "fragmentos" | "hallazgo";

/**
 * La hoja del pliego como placa: fondo de película azul grisáceo y trazo claro, con ruido de grano.
 * `modo` decide qué se marca encima: nada, la barra de lectura, los fragmentos o el hallazgo.
 * `ciclo` enlaza el trazo ámbar con el reloj de la animación del héroe.
 */
export function PlacaPliego({
  modo = "completo",
  ciclo = false,
  etiqueta = "PLIEGO_E2E.PDF",
  className,
}: {
  modo?: ModoPlaca;
  ciclo?: boolean;
  etiqueta?: string;
  className?: string;
}) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const marca = modo === "hallazgo" || modo === "completo";
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={cn("block h-full w-full", className)} role="img" aria-label="Hoja de un pliego vista como placa radiográfica">
      <defs>
        <radialGradient id={`f${uid}`} cx="50%" cy="42%" r="75%">
          <stop offset="0" stopColor="#2b3947" />
          <stop offset="1" stopColor="#121a24" />
        </radialGradient>
        <filter id={`g${uid}`} x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="r" />
          <feColorMatrix type="saturate" values="0" />
          <feComponentTransfer>
            <feFuncA type="linear" slope="0.5" />
          </feComponentTransfer>
        </filter>
        <filter id={`c${uid}`} x="-5%" y="-20%" width="110%" height="140%">
          <feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="2" seed="3" result="t" />
          <feDisplacementMap in="SourceGraphic" in2="t" scale="3.2" />
        </filter>
        <filter id={`b${uid}`}>
          <feGaussianBlur stdDeviation="0.45" />
        </filter>
      </defs>

      <rect width={W} height={H} fill={`url(#f${uid})`} />

      {/* Rótulo de la placa */}
      <g fontFamily="var(--font-mono)" fill="#cfe3ea" fontSize="8.5" letterSpacing="0.9">
        <text x="30" y="34" opacity="0.85">MEDTENDER · LIC-2027-014</text>
        <text x="30" y="47" opacity="0.6">{etiqueta} · 20.11.2026</text>
        <text x={W - 30} y="34" textAnchor="end" opacity="0.85">EJEMPLO</text>
      </g>
      <g fill="#e4f3f8">
        <rect x="30" y="62" width="196" height="9" rx="2" opacity="0.8" />
        <rect x="30" y="78" width="124" height="4" rx="2" opacity="0.4" />
        <rect x="30" y="196" width="108" height="5" rx="2" opacity="0.75" />
      </g>

      {/* Líneas de texto */}
      <g fill="#d7ecf3" filter={`url(#b${uid})`}>
        {LINEAS.map((l) => (
          <rect key={l.y} x={l.x ?? 30} y={l.y} width={l.w} height="4.2" rx="2" opacity={l.o} />
        ))}
      </g>

      {/* Tabla */}
      <g stroke="#cfe3ea" strokeOpacity="0.45" strokeWidth="1" fill="none">
        <rect x="30" y="352" width="350" height="72" rx="2" />
        <path d="M30 376h350M30 400h350M130 352v72M250 352v72" />
      </g>
      <g fill="#d7ecf3" opacity="0.5">
        <rect x="40" y="361" width="60" height="4" rx="2" />
        <rect x="140" y="361" width="80" height="4" rx="2" />
        <rect x="260" y="361" width="44" height="4" rx="2" />
        <rect x="40" y="385" width="48" height="4" rx="2" />
        <rect x="140" y="385" width="96" height="4" rx="2" />
        <rect x="260" y="385" width="70" height="4" rx="2" />
        <rect x="40" y="409" width="70" height="4" rx="2" />
        <rect x="140" y="409" width="60" height="4" rx="2" />
        <rect x="260" y="409" width="56" height="4" rx="2" />
      </g>

      {/* Sello y firma de la hoja */}
      <g fill="none" stroke="#cfe3ea" strokeOpacity="0.55" strokeWidth="1.4">
        <circle cx="338" cy="462" r="20" />
        <circle cx="338" cy="462" r="14" strokeDasharray="2 3" />
        <path d="M34 466c10-14 16 10 26-2s12 8 22-4 14 6 24-2" strokeLinecap="round" />
      </g>

      {/* Grano de película */}
      <rect width={W} height={H} filter={`url(#g${uid})`} opacity="0.22" style={{ mixBlendMode: "soft-light" }} />

      {/* Barra de lectura (paso 1) */}
      {modo === "escaneo" && (
        <g>
          <rect x="14" y="214" width={W - 28} height="2" fill="#7cd4e6" />
          <rect x="14" y="150" width={W - 28} height="64" fill="#7cd4e6" opacity="0.1" />
        </g>
      )}

      {/* Fragmentos (paso 2) */}
      {modo === "fragmentos" &&
        FRAGMENTOS.map((f) => (
          <g key={f.n}>
            <rect x="22" y={f.y} width={W - 44} height={f.h} rx="2" fill="none" stroke="#7cd4e6" strokeWidth="1.2" strokeDasharray="5 4" />
            <rect x="22" y={f.y - 9} width="32" height="12" fill="#7cd4e6" />
            <text x="26" y={f.y} fontFamily="var(--font-mono)" fontSize="8.5" fontWeight="700" fill="#07101c">
              {f.n}
            </text>
          </g>
        ))}

      {/* El hallazgo: círculo de rotulador de cera y su anotación */}
      {marca && (
        <g className={ciclo ? "ciclo-marca" : undefined} filter={`url(#c${uid})`}>
          <path
            pathLength={1}
            style={{ ["--largo" as string]: 1 }}
            className={ciclo ? "ciclo-trazo" : undefined}
            d="M34 238C28 214 96 204 190 205C290 206 346 214 346 236C346 262 262 268 170 266C84 264 36 262 30 244C27 232 46 220 74 214"
            fill="none"
            stroke="#ffc247"
            strokeWidth="3.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray={ciclo ? undefined : 1}
            strokeDashoffset={ciclo ? undefined : 0}
          />
        </g>
      )}
      {marca && (
        <g className={ciclo ? "ciclo-nota" : undefined}>
          <g filter={`url(#c${uid})`}>
            <path d="M118 270C110 288 114 302 104 316" fill="none" stroke="#ffc247" strokeWidth="3" strokeLinecap="round" />
            <path d="M104 316l1-12M104 316l10-6" fill="none" stroke="#ffc247" strokeWidth="3" strokeLinecap="round" />
          </g>
          <text
            x="64"
            y="346"
            transform="rotate(-3 64 346)"
            fill="#ffc247"
            fontFamily="var(--font-cera)"
            fontSize="36"
          >
            [1] garantía: 12 meses
          </text>
        </g>
      )}
    </svg>
  );
}

/** Pinza metálica que sujeta la placa por arriba. */
export function Pinza({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "absolute top-0 z-20 h-7 w-14 rounded-b-lg border border-black/40 bg-gradient-to-b from-[#8696a3] via-[#56636f] to-[#2d3640] shadow-[0_6px_8px_-3px_rgb(0_0_0/0.55)]",
        className,
      )}
      aria-hidden
    >
      <span className="absolute inset-x-2 top-1.5 h-1 rounded-full bg-white/35" />
      <span className="absolute inset-x-3 bottom-1.5 h-px bg-black/50" />
    </span>
  );
}

/**
 * Negatoscopio: marco metálico, superficie de luz fría y pinzas arriba. Lo que se pone dentro
 * (`children`) es la placa. Tiene una razón: la placa es lo único oscuro sobre una superficie clara.
 */
export function PanelLuz({
  children,
  className,
  pinzas = true,
  luz = false,
}: {
  children: ReactNode;
  className?: string;
  pinzas?: boolean;
  /** Sube el brillo del panel mientras no hay placa (acompaña al ciclo del héroe). */
  luz?: boolean;
}) {
  return (
    <div
      className={cn(
        "relative rounded-[0.6rem] border-[11px] border-[#2c3641] bg-[#2c3641] shadow-[0_40px_60px_-30px_rgb(0_0_0/0.95),inset_0_0_0_1px_rgb(255_255_255/0.08)]",
        className,
      )}
    >
      <div className="panel-luz absolute inset-0 rounded-[0.15rem]" aria-hidden />
      {luz && <div className="ciclo-luz absolute inset-0 bg-white/50" aria-hidden />}
      {pinzas && (
        <>
          <Pinza className="left-[16%]" />
          <Pinza className="right-[16%]" />
        </>
      )}
      {children}
    </div>
  );
}

/** Orilla de película: la fila de perforaciones que separa secciones. */
export function Perforaciones({ className, claro = false }: { className?: string; claro?: boolean }) {
  return (
    <div
      className={cn("h-3 w-full", className)}
      style={{
        backgroundImage: `linear-gradient(90deg, ${claro ? "#05080e" : "#e4f3f8"} 0 10px, transparent 10px 22px)`,
        backgroundSize: "22px 7px",
        backgroundRepeat: "repeat-x",
        backgroundPosition: "0 center",
        opacity: claro ? 0.35 : 0.16,
        maskImage: "linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent)",
      }}
      aria-hidden
    />
  );
}

/** Placa en blanco: decoración de estados vacíos (una película sin estudio). */
export function PlacaVacia({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 160 200" className={className} fill="none" aria-hidden>
      <rect x="6" y="14" width="148" height="180" rx="4" fill="#1b2430" stroke="#e4f3f8" strokeOpacity="0.25" />
      <path d="M122 14v22a2 2 0 0 0 2 2h30" stroke="#e4f3f8" strokeOpacity="0.2" />
      <g fill="#cfe3ea">
        <rect x="22" y="52" width="70" height="6" rx="3" opacity="0.35" />
        <rect x="22" y="74" width="116" height="4" rx="2" opacity="0.2" />
        <rect x="22" y="86" width="104" height="4" rx="2" opacity="0.2" />
        <rect x="22" y="98" width="112" height="4" rx="2" opacity="0.2" />
      </g>
      <path d="M26 142c22-26 56-26 78-4s30 6 36-6" stroke="#ffc247" strokeOpacity="0.85" strokeWidth="3" strokeLinecap="round" strokeDasharray="1 9" />
      <rect x="50" y="2" width="22" height="16" rx="3" fill="#56636f" />
      <rect x="92" y="2" width="22" height="16" rx="3" fill="#56636f" />
    </svg>
  );
}
