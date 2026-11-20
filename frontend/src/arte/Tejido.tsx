import { useEffect, useRef } from "react";
import { cn } from "../lib/cn";

/**
 * Tejido teñido con hematoxilina y eosina, generado en código: un mosaico de células (Voronoi con
 * semillas jitterizadas), citoplasma rosa con regiones lavanda, membranas más oscuras, núcleos
 * índigo con cromatina y fibras de colágeno. Se dibuja UNA vez por tamaño (nada se anima aquí):
 * es fondo, no efecto.
 */

function mulberry32(semilla: number) {
  let a = semilla;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

type RGB = [number, number, number];
const EOSINA: RGB[] = [
  [247, 190, 214],
  [243, 160, 195],
  [250, 208, 226],
  [238, 138, 180],
  [246, 176, 205],
];
const LAVANDA: RGB[] = [
  [206, 198, 245],
  [188, 178, 238],
  [222, 214, 250],
];
const mezcla = (a: RGB, b: RGB, t: number): RGB => [
  a[0] + (b[0] - a[0]) * t,
  a[1] + (b[1] - a[1]) * t,
  a[2] + (b[2] - a[2]) * t,
];

type Props = {
  className?: string;
  semilla?: number;
  /** Tamaño medio de una célula en px CSS. */
  celula?: number;
  /** 0 = lavado casi blanco, 1 = tinción plena. */
  tinte?: number;
  /** Proporción de la superficie en tono hematoxilina (lavanda). */
  lavanda?: number;
};

export function Tejido({ className, semilla = 7, celula = 54, tinte = 1, lavanda = 0.35 }: Props) {
  const lienzo = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = lienzo.current;
    if (!canvas) return;
    let temporizador = 0;

    const pintar = () => {
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const caja = canvas.getBoundingClientRect();
      if (caja.width < 8 || caja.height < 8) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      const W = Math.round(caja.width * dpr);
      const H = Math.round(caja.height * dpr);
      canvas.width = W;
      canvas.height = H;

      // Resolución de cálculo reducida: el tejido es suave por naturaleza.
      const escala = Math.min(0.5, 760 / W);
      const w = Math.max(40, Math.round(W * escala));
      const h = Math.max(40, Math.round(H * escala));
      const tamano = (celula * dpr) * escala; // px de cálculo por célula
      const azar = mulberry32(semilla);

      // Semillas: rejilla con jitter (reparto parejo, sin cúmulos feos).
      const cols = Math.ceil(w / tamano) + 2;
      const filas = Math.ceil(h / tamano) + 2;
      const semillas: { x: number; y: number; color: RGB; nucleo: boolean; r: number }[] = [];
      const celdas: number[][] = Array.from({ length: cols * filas }, () => []);
      // Ruido de baja frecuencia: decide dónde el tejido vira a lavanda (otro tipo celular).
      const o1 = azar() * 10;
      const o2 = azar() * 10;
      const region = (x: number, y: number) =>
        0.5 + 0.5 * Math.sin(x * 0.011 + o1) * Math.cos(y * 0.013 + o2) + 0.25 * Math.sin((x + y) * 0.021 + o2);
      for (let cy = 0; cy < filas; cy++) {
        for (let cx = 0; cx < cols; cx++) {
          const x = (cx - 0.5 + 0.15 + azar() * 0.7) * tamano;
          const y = (cy - 0.5 + 0.15 + azar() * 0.7) * tamano;
          const esLavanda = region(x / escala, y / escala) * 1 > 1 - lavanda * 1.2;
          const paleta = esLavanda ? LAVANDA : EOSINA;
          semillas.push({
            x,
            y,
            color: paleta[Math.floor(azar() * paleta.length)]!,
            nucleo: azar() < 0.78,
            r: tamano * (0.2 + azar() * 0.1),
          });
          celdas[cy * cols + cx]!.push(semillas.length - 1);
        }
      }

      const imagen = ctx.createImageData(w, h);
      const px = imagen.data;
      const base: RGB = [252, 240, 247];
      for (let y = 0; y < h; y++) {
        const gy = Math.floor(y / tamano) + 1;
        for (let x = 0; x < w; x++) {
          const gx = Math.floor(x / tamano) + 1;
          let d1 = 1e9;
          let d2 = 1e9;
          let mejor = -1;
          for (let j = -1; j <= 1; j++) {
            for (let i = -1; i <= 1; i++) {
              const gi = (gy + j) * cols + (gx + i);
              if (gi < 0 || gi >= celdas.length) continue;
              for (const k of celdas[gi]!) {
                const s = semillas[k]!;
                const d = Math.hypot(x - s.x, y - s.y);
                if (d < d1) {
                  d2 = d1;
                  d1 = d;
                  mejor = k;
                } else if (d < d2) d2 = d;
              }
            }
          }
          const s = semillas[mejor];
          let c: RGB = base;
          if (s) {
            // Citoplasma más claro en el centro y más denso hacia la membrana.
            const borde = Math.min(1, d1 / (tamano * 0.62));
            c = mezcla(s.color, [s.color[0] * 0.9, s.color[1] * 0.78, s.color[2] * 0.9], borde * borde);
            // Membrana: donde la segunda célula casi empata.
            const m = Math.max(0, 1 - (d2 - d1) / (tamano * 0.1));
            c = mezcla(c, [196, 74, 132], m * 0.85);
          }
          const idx = (y * w + x) * 4;
          // «tinte» diluye hacia el fondo para los lavados.
          const k = tinte;
          px[idx] = base[0] + (c[0] - base[0]) * k;
          px[idx + 1] = base[1] + (c[1] - base[1]) * k;
          px[idx + 2] = base[2] + (c[2] - base[2]) * k;
          px[idx + 3] = 255;
        }
      }

      // Se dibuja a baja resolución y se amplía con suavizado.
      const aux = document.createElement("canvas");
      aux.width = w;
      aux.height = h;
      aux.getContext("2d")!.putImageData(imagen, 0, 0);
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      ctx.filter = "blur(0.8px)";
      ctx.drawImage(aux, 0, 0, W, H);
      ctx.filter = "none";

      // Núcleos de hematoxilina con cromatina, a resolución completa.
      const f = 1 / escala;
      for (const s of semillas) {
        if (!s.nucleo) continue;
        const cx = s.x * f;
        const cy = s.y * f;
        const rx = s.r * f * (0.9 + azar() * 0.35);
        const ry = rx * (0.72 + azar() * 0.3);
        ctx.save();
        ctx.globalAlpha = 0.35 + 0.65 * tinte;
        ctx.translate(cx, cy);
        ctx.rotate(azar() * Math.PI);
        const g = ctx.createRadialGradient(-rx * 0.2, -ry * 0.2, 0, 0, 0, rx);
        g.addColorStop(0, "#6a5cd6");
        g.addColorStop(0.6, "#4a3dbf");
        g.addColorStop(1, "#2c2290");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.ellipse(0, 0, rx, ry, 0, 0, Math.PI * 2);
        ctx.fill();
        // Cromatina: motas más claras y más oscuras dentro del núcleo.
        for (let k = 0; k < 5; k++) {
          ctx.fillStyle = k % 2 ? "rgba(255,255,255,0.22)" : "rgba(20,14,80,0.4)";
          ctx.beginPath();
          ctx.arc((azar() - 0.5) * rx * 1.1, (azar() - 0.5) * ry * 1.1, rx * (0.08 + azar() * 0.1), 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();
      }

      // Fibras de colágeno: trazos finos, ondulados y translúcidos.
      ctx.save();
      ctx.globalAlpha = 0.4 * tinte;
      ctx.lineCap = "round";
      for (let n = 0; n < Math.max(4, Math.round((caja.width * caja.height) / 90000)); n++) {
        ctx.strokeStyle = n % 2 ? "rgba(255,255,255,0.8)" : "rgba(200,70,130,0.5)";
        ctx.lineWidth = (0.8 + azar() * 1.4) * dpr;
        const x0 = azar() * W;
        const y0 = azar() * H;
        const largo = (180 + azar() * 360) * dpr;
        const ang = azar() * Math.PI;
        ctx.beginPath();
        for (let t = 0; t <= 1; t += 0.05) {
          const x = x0 + Math.cos(ang) * largo * t + Math.sin(t * 9 + n) * 10 * dpr;
          const y = y0 + Math.sin(ang) * largo * t + Math.cos(t * 7 + n) * 10 * dpr;
          t === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.stroke();
      }
      ctx.restore();
    };

    pintar();
    const observador = new ResizeObserver(() => {
      window.clearTimeout(temporizador);
      temporizador = window.setTimeout(pintar, 180);
    });
    observador.observe(canvas);
    return () => {
      window.clearTimeout(temporizador);
      observador.disconnect();
    };
  }, [semilla, celula, tinte, lavanda]);

  return <canvas ref={lienzo} className={cn("pointer-events-none absolute inset-0 size-full", className)} aria-hidden />;
}
