import { useId, useMemo } from "react";
import { cn } from "../lib/cn";

/** Pseudoaleatorio determinista: el paisaje es siempre el mismo. */
function azar(semilla: number) {
  let s = semilla;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

/** Una cordillera: poligonal quebrada por octavas de ruido, cerrada hacia abajo. */
function cordillera(semilla: number, base: number, amplitud: number, ancho = 1600) {
  const r = azar(semilla);
  const fases = [r() * 6.28, r() * 6.28, r() * 6.28];
  const pts: string[] = [];
  for (let x = 0; x <= ancho; x += 16) {
    const t = x / ancho;
    const y =
      base -
      amplitud *
        (0.55 * Math.sin(t * 5.2 + fases[0]) + 0.3 * Math.sin(t * 11.7 + fases[1]) + 0.15 * Math.sin(t * 27 + fases[2]) + 0.3 * (r() - 0.5));
    pts.push(`${x},${y.toFixed(1)}`);
  }
  return `M0,900 L${pts.join(" L")} L${ancho},900 Z`;
}

/**
 * Hora azul entre montañas, dibujada en código: cielo frío, luna velada, cuatro cordilleras con bruma
 * entre capas y una sola luz lejana (el escritorio solitario). Se oscurece hacia el lienzo para que
 * el texto se lea sin velo extra. Sin imágenes: cumple la CSP y no pesa.
 */
export function Montanas({ className, intensidad = 1 }: { className?: string; intensidad?: number }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");
  const capas = useMemo(
    () => [
      { d: cordillera(3, 520, 90), fill: "#3a4062", o: 0.9 },
      { d: cordillera(8, 600, 120), fill: "#2c3050", o: 1 },
      { d: cordillera(13, 690, 110), fill: "#222540", o: 1 },
      { d: cordillera(21, 790, 80), fill: "#191a2d", o: 1 },
    ],
    [],
  );
  return (
    <div className={cn("absolute inset-0 -z-10 overflow-hidden bg-sala", className)} aria-hidden>
      <div
        className="absolute inset-0"
        style={{ background: "linear-gradient(180deg,#232845 0%,#323859 34%,#4b5173 58%,#2a2e4d 80%,#171721 100%)", opacity: intensidad }}
      />
      {/* Luna velada */}
      <div className="absolute left-[68%] top-[12%] size-24 rounded-full bg-[radial-gradient(circle,rgb(237_237_243/0.5),rgb(237_237_243/0.08)_55%,transparent_70%)] blur-[2px]" />
      <svg className="absolute inset-0 size-full" viewBox="0 0 1600 900" preserveAspectRatio="xMidYMax slice">
        <defs>
          <filter id={`b${id}`} x="-10%" y="-30%" width="120%" height="160%">
            <feTurbulence type="fractalNoise" baseFrequency="0.0022 0.011" numOctaves="4" seed="9" />
            <feColorMatrix type="matrix" values="0 0 0 0 0.8  0 0 0 0 0.82  0 0 0 0 0.95  0 0 0 1.7 -0.72" />
          </filter>
          <filter id={`g${id}`} x="0" y="0" width="100%" height="100%">
            <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="5" />
            <feColorMatrix type="saturate" values="0" />
          </filter>
          <linearGradient id={`v${id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#000" />
            <stop offset="0.35" stopColor="#fff" />
            <stop offset="0.65" stopColor="#fff" />
            <stop offset="1" stopColor="#000" />
          </linearGradient>
          <linearGradient id={`m${id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#c3c3dc" stopOpacity="0" />
            <stop offset="0.5" stopColor="#c3c3dc" stopOpacity="0.24" />
            <stop offset="1" stopColor="#c3c3dc" stopOpacity="0" />
          </linearGradient>
        </defs>
        {capas.map((c, i) => (
          <g key={i}>
            <path d={c.d} fill={c.fill} opacity={c.o} />
            {/* Bruma que se asienta sobre cada cordillera */}
            <rect x="0" y={500 + i * 95} width="1600" height="150" fill={`url(#m${id})`} />
            <mask id={`k${id}${i}`} maskUnits="userSpaceOnUse" x="-80" y={470 + i * 95} width="1760" height="200">
              <rect x="-80" y={470 + i * 95} width="1760" height="200" fill={`url(#v${id})`} />
            </mask>
            <g mask={`url(#k${id}${i})`}><g className="motion-safe:animate-deriva" style={{ animationDuration: `${26 + i * 7}s` }}>
              <rect x="-80" y={470 + i * 95} width="1760" height="200" filter={`url(#b${id})`} opacity={0.35 - i * 0.05} />
            </g></g>
          </g>
        ))}
        {/* El escritorio solitario: una sola luz */}
        <g>
          <circle cx="1070" cy="647" r="9" fill="#ededf3" opacity="0.1" />
          <rect x="1066" y="643" width="8" height="5" fill="#ededf3" opacity="0.92" />
        </g>
        <rect width="1600" height="900" filter={`url(#g${id})`} opacity="0.1" style={{ mixBlendMode: "overlay" }} />
      </svg>
      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgb(23_23_33/0.35)_0%,transparent_30%,transparent_66%,#171721_100%)]" />
    </div>
  );
}
