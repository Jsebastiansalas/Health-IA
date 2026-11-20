import { useEffect, useRef } from "react";
import { cn } from "../lib/cn";

/**
 * El mecanismo de MedTender en un solo cuadro: una hoja de pliego se deshace en palabras que
 * vuelan hasta convertirse en estrellas de un espacio vectorial; de la estrella citada nace una
 * cita verificable y la hoja ya no existe. Ciclo de 11 s dibujado en un canvas 2D con el mismo
 * reloj que las superposiciones CSS (`.ciclo-cita`, `.ciclo-sello`).
 */

const CICLO = 11; // segundos
const LADO = 560; // espacio de diseño cuadrado
const HOJA = { cx: 175, cy: 300, ancho: 210, alto: 280, giro: (-7 * Math.PI) / 180 };

type Palabra = { sx: number; sy: number; w: number; h: number; inicio: number; fuerte: boolean; destino: number };
type Estrella = { x: number; y: number; r: number };

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

function construir() {
  const azar = mulberry32(20270519);
  const palabras: Palabra[] = [];
  const filas = 16;
  const margen = 22;
  const util = HOJA.ancho - margen * 2;
  for (let f = 0; f < filas; f++) {
    const y = -HOJA.alto / 2 + 44 + f * 15.2;
    let x = -HOJA.ancho / 2 + margen;
    const titulo = f === 0;
    while (x < -HOJA.ancho / 2 + margen + util - 18) {
      const w = titulo ? 54 + azar() * 22 : 16 + azar() * 30;
      const resto = -HOJA.ancho / 2 + margen + util - x;
      const ancho = Math.min(w, resto);
      if (ancho < 9) break;
      palabras.push({ sx: x, sy: y, w: ancho, h: titulo ? 7 : 4.6, inicio: 0, fuerte: titulo, destino: 0 });
      x += ancho + 6;
      if (!titulo && azar() < 0.07) break; // fin de párrafo
    }
    if (f === 4 || f === 9) x = 0; // sangría natural entre párrafos
  }
  // Orden de desprendimiento: de arriba abajo con un poco de desorden.
  palabras.forEach((p, i) => (p.inicio = 1.3 + i * 0.058 + azar() * 0.18));

  // Estrellas: seis racimos (fragmentos de un mismo apartado) a la derecha de la hoja.
  const racimos = [
    [420, 110], [500, 205], [405, 255], [470, 330], [380, 395], [505, 440],
  ] as const;
  const estrellas: Estrella[] = [];
  const porRacimo = Math.ceil(palabras.length / racimos.length);
  racimos.forEach(([cx, cy]) => {
    for (let k = 0; k < porRacimo; k++) {
      const ang = azar() * Math.PI * 2;
      const rad = 6 + azar() * 40;
      estrellas.push({ x: cx + Math.cos(ang) * rad, y: cy + Math.sin(ang) * rad * 0.8, r: 1.6 + azar() * 1.9 });
    }
  });
  palabras.forEach((p, i) => (p.destino = i % estrellas.length));

  const aristas: [number, number][] = [];
  estrellas.forEach((a, i) => {
    const cercanas = estrellas
      .map((b, j) => ({ j, d: Math.hypot(a.x - b.x, a.y - b.y) }))
      .filter((c) => c.j > i && c.d < 62)
      .sort((u, v) => u.d - v.d)
      .slice(0, 2);
    cercanas.forEach((c) => aristas.push([i, c.j]));
  });

  // La estrella citada: la más cercana al centro del racimo del medio.
  let citada = 0;
  let mejor = Infinity;
  estrellas.forEach((e, i) => {
    const d = Math.hypot(e.x - 405, e.y - 255);
    if (d < mejor) {
      mejor = d;
      citada = i;
    }
  });
  return { palabras, estrellas, aristas, citada };
}

const GEOMETRIA = construir();
const FIN_VUELO = (p: Palabra) => p.inicio + 1.8;

const acotar = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const suave = (x: number) => x * x * (3 - 2 * x);
const mezclar = (a: number, b: number, t: number) => a + (b - a) * t;

export function HojaDisuelta({ className }: { className?: string }) {
  const lienzo = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = lienzo.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const reducido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    const { palabras, estrellas, aristas, citada } = GEOMETRIA;
    let ancho = 0;
    let alto = 0;
    let raf = 0;
    let ultimo = 0;
    let visible = true;
    const origen = performance.now();

    const aMundo = (lx: number, ly: number, flotar: number) => {
      const c = Math.cos(HOJA.giro);
      const s = Math.sin(HOJA.giro);
      return { x: HOJA.cx + lx * c - ly * s, y: HOJA.cy + flotar + lx * s + ly * c };
    };

    const dibujar = (t: number) => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, ancho, alto);
      const escala = Math.min(ancho, alto) / LADO;
      ctx.translate((ancho - LADO * escala) / 2, (alto - LADO * escala) / 2);
      ctx.scale(escala, escala);

      const flotar = Math.sin((t / CICLO) * Math.PI * 4) * 4;
      const alfaHoja = t < 6.4 ? 1 : t < 7.4 ? 1 - suave((t - 6.4) / 1.0) : t > 10.2 ? suave((t - 10.2) / 0.8) : 0;
      const alfaGlobal = t > 10.2 ? 1 - suave((t - 10.2) / 0.8) : 1; // el cielo se apaga antes de reiniciar

      // --- Hoja ---
      if (alfaHoja > 0.01) {
        ctx.save();
        ctx.globalAlpha = alfaHoja;
        ctx.translate(HOJA.cx, HOJA.cy + flotar);
        ctx.rotate(HOJA.giro);
        ctx.shadowColor = "rgba(0,0,0,0.55)";
        ctx.shadowBlur = 34;
        ctx.shadowOffsetY = 22;
        const papel = ctx.createLinearGradient(0, -HOJA.alto / 2, 0, HOJA.alto / 2);
        papel.addColorStop(0, "#ffffff");
        papel.addColorStop(1, "#f1eafa");
        ctx.fillStyle = papel;
        ctx.beginPath();
        ctx.roundRect(-HOJA.ancho / 2, -HOJA.alto / 2, HOJA.ancho, HOJA.alto, 9);
        ctx.fill();
        ctx.shadowColor = "transparent";
        ctx.fillStyle = "#4b3fc9";
        ctx.font = '600 8px "JetBrains Mono Variable", monospace';
        ctx.fillText("Pliego_E2E.pdf", -HOJA.ancho / 2 + 22, -HOJA.alto / 2 + 24);
        ctx.fillStyle = "#8f87d6";
        ctx.fillText("3 págs · 214 KB", -HOJA.ancho / 2 + 22, -HOJA.alto / 2 + 34);
        ctx.restore();
      }

      // --- Aristas (cuando sus dos estrellas ya llegaron) ---
      const llegada = new Map<number, number>();
      for (const p of palabras) {
        const llega = FIN_VUELO(p);
        const previa = llegada.get(p.destino);
        if (previa === undefined || llega < previa) llegada.set(p.destino, llega);
      }
      const luzAristas = acotar((t - 5.2) / 1.4) * alfaGlobal;
      if (luzAristas > 0.01) {
        for (const [i, j] of aristas) {
          const a = llegada.get(i);
          const b = llegada.get(j);
          if (a === undefined || b === undefined || t < Math.max(a, b)) continue;
          const A = estrellas[i]!;
          const B = estrellas[j]!;
          ctx.strokeStyle = `rgba(75,63,201,${0.3 * luzAristas})`;
          ctx.lineWidth = 0.8;
          ctx.beginPath();
          ctx.moveTo(A.x, A.y);
          ctx.lineTo(B.x, B.y);
          ctx.stroke();
        }
      }

      // --- Palabras en vuelo y estrellas ---
      for (const p of palabras) {
        const progreso = acotar((t - p.inicio) / 1.8);
        const destino = estrellas[p.destino]!;
        if (progreso <= 0) {
          if (alfaHoja > 0.01) {
            const m = aMundo(p.sx + p.w / 2, p.sy, flotar);
            ctx.save();
            ctx.globalAlpha = alfaHoja;
            ctx.translate(m.x, m.y);
            ctx.rotate(HOJA.giro);
            ctx.fillStyle = p.fuerte ? "#2f2699" : "#9a92dc";
            ctx.beginPath();
            ctx.roundRect(-p.w / 2, -p.h / 2, p.w, p.h, 2);
            ctx.fill();
            ctx.restore();
          }
          continue;
        }
        if (progreso < 1) {
          const e = suave(progreso);
          const o = aMundo(p.sx + p.w / 2, p.sy, flotar);
          // Trayectoria curva: se separa de la recta en perpendicular a mitad de camino.
          const dx = destino.x - o.x;
          const dy = destino.y - o.y;
          const norma = Math.hypot(dx, dy) || 1;
          const arco = Math.sin(progreso * Math.PI) * 38 * (p.destino % 2 ? 1 : -1);
          const x = mezclar(o.x, destino.x, e) + (-dy / norma) * arco;
          const y = mezclar(o.y, destino.y, e) + (dx / norma) * arco;
          const w = mezclar(p.w, 4.5, e);
          const h = mezclar(p.h, 4.5, e);
          const k = acotar(e * 1.4);
          const verde = Math.round(mezclar(146, 48, k));
          ctx.fillStyle = `rgb(${Math.round(mezclar(154, 217, k))},${verde},${Math.round(mezclar(220, 111, k))})`;
          ctx.globalAlpha = alfaGlobal;
          ctx.beginPath();
          ctx.roundRect(x - w / 2, y - h / 2, w, h, Math.min(w, h) / 2);
          ctx.fill();
          ctx.globalAlpha = 1;
        }
      }

      // Estrellas que ya llegaron.
      llegada.forEach((llega, i) => {
        if (t < llega) return;
        const s = estrellas[i]!;
        const destello = Math.max(0, 1 - (t - llega) / 0.5);
        const esCitada = i === citada;
        ctx.globalAlpha = alfaGlobal;
        const halo = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, 10 + destello * 10 + (esCitada ? 8 : 0));
        halo.addColorStop(0, `rgba(244,114,166,${0.55 + destello * 0.4})`);
        halo.addColorStop(1, "rgba(244,114,166,0)");
        ctx.fillStyle = halo;
        ctx.fillRect(s.x - 24, s.y - 24, 48, 48);
        ctx.fillStyle = esCitada && t > 5.8 ? "#1a1446" : "#4b3fc9";
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r + (esCitada && t > 5.8 ? 1.4 : 0), 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1;
      });

      // --- La estrella citada llama a la cita ---
      if (t > 5.7 && t < 10.6) {
        const s = estrellas[citada]!;
        const a = acotar((t - 5.7) / 0.7) * alfaGlobal;
        for (let k = 0; k < 2; k++) {
          const fase = ((t * 0.9 + k * 0.5) % 1);
          ctx.strokeStyle = `rgba(217,48,111,${(1 - fase) * 0.7 * a})`;
          ctx.lineWidth = 1.2;
          ctx.beginPath();
          ctx.arc(s.x, s.y, 5 + fase * 22, 0, Math.PI * 2);
          ctx.stroke();
        }
        const fin = { x: 392, y: 468 };
        ctx.setLineDash([3, 5]);
        ctx.lineDashOffset = -t * 14;
        ctx.strokeStyle = `rgba(26,20,70,${0.8 * a})`;
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.quadraticCurveTo(s.x - 60, (s.y + fin.y) / 2, fin.x, fin.y);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    };

    const medir = () => {
      const caja = canvas.getBoundingClientRect();
      ancho = caja.width;
      alto = caja.height;
      canvas.width = Math.round(ancho * dpr);
      canvas.height = Math.round(alto * dpr);
      dibujar(reducido ? 8.4 : ((performance.now() - origen) / 1000) % CICLO);
    };

    const avanzar = (ahora: number) => {
      raf = requestAnimationFrame(avanzar);
      if (ahora - ultimo < 1000 / 40) return;
      ultimo = ahora;
      dibujar(((ahora - origen) / 1000) % CICLO);
    };
    const arrancar = () => {
      if (reducido || raf || !visible || document.hidden) return;
      raf = requestAnimationFrame(avanzar);
    };
    const parar = () => {
      cancelAnimationFrame(raf);
      raf = 0;
    };
    const alVisibilidad = () => (document.hidden ? parar() : arrancar());

    const observador = new ResizeObserver(medir);
    observador.observe(canvas);
    const vista = new IntersectionObserver(([e]) => {
      visible = !!e?.isIntersecting;
      visible ? arrancar() : parar();
    });
    vista.observe(canvas);
    document.addEventListener("visibilitychange", alVisibilidad);
    medir();
    arrancar();
    return () => {
      parar();
      observador.disconnect();
      vista.disconnect();
      document.removeEventListener("visibilitychange", alVisibilidad);
    };
  }, []);

  return <canvas ref={lienzo} className={cn("size-full", className)} aria-hidden />;
}
