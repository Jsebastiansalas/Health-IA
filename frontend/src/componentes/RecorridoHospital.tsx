import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "../lib/cn";

/** Una parada del recorrido: la escena fija y el texto que la acompaña. */
export interface ParadaRecorrido {
  titulo: string;
  texto: string;
}

const RUTA = "/recorrido";
const escena = (i: number) => `${RUTA}/escena-${i + 1}.webp`;
const escenaMovil = (i: number) => `${RUTA}/escena-${i + 1}-movil.webp`;
const tramo = (i: number) => `${RUTA}/tramo-${i + 1}.mp4`;

/** Pantallas de scroll que dura cada parada y cada tramo de video entre paradas. */
const PESO_PARADA = 0.8;
const PESO_TRAMO = 0.9;
/** Fracción del tramo en la que el video se funde con la imagen fija de cada extremo. */
const FUNDIDO = 0.14;
/** Color del fondo de las escenas, medido en las imágenes: el escenario lo usa para que no se vean bordes. */
const FONDO_ESCENA = "#f0f3f7";

/**
 * Dónde se dibuja cada escena: a la derecha, sin recortar, con los bordes desvanecidos sobre el fondo
 * para que el texto de la izquierda nunca quede encima del diorama.
 */
const ESCENARIO =
  "absolute right-0 top-1/2 aspect-video w-[76%] max-h-full -translate-y-1/2 object-contain [mask-image:radial-gradient(ellipse_50%_50%_at_center,black_62%,transparent_100%)]";

const limitar = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const suave = (x: number) => {
  const t = limitar(x);
  return t * t * (3 - 2 * t);
};

type Segmento = { tipo: "parada" | "tramo"; i: number; inicio: number; fin: number };

function segmentos(n: number): { lista: Segmento[]; total: number } {
  const lista: Segmento[] = [];
  let x = 0;
  for (let i = 0; i < n; i++) {
    lista.push({ tipo: "parada", i, inicio: x, fin: x + PESO_PARADA });
    x += PESO_PARADA;
    if (i < n - 1) {
      lista.push({ tipo: "tramo", i, inicio: x, fin: x + PESO_TRAMO });
      x += PESO_TRAMO;
    }
  }
  return { lista, total: x };
}

/** El recorrido animado solo se monta en pantallas anchas con ratón y sin movimiento reducido. */
function usarRecorridoAnimado() {
  const consulta = "(min-width: 1024px) and (hover: hover) and (prefers-reduced-motion: no-preference)";
  const [activo, setActivo] = useState(() => typeof window !== "undefined" && !!window.matchMedia?.(consulta).matches);
  useEffect(() => {
    const mq = window.matchMedia?.(consulta);
    if (!mq) return;
    const cambiar = () => setActivo(mq.matches);
    mq.addEventListener("change", cambiar);
    return () => mq.removeEventListener("change", cambiar);
  }, []);
  return activo;
}

/**
 * Recorrido por un hospital en miniatura que avanza con el scroll: seis escenas fijas unidas por cinco
 * tramos de video que empiezan y terminan exactamente en ellas. El scroll mueve el tiempo del video.
 * En el celular, con movimiento reducido o sin ratón, se muestran las seis escenas fijas con su texto.
 */
export function RecorridoHospital({ titulo, paradas }: { titulo: string; paradas: ParadaRecorrido[] }) {
  const animado = usarRecorridoAnimado();
  return animado ? <RecorridoAnimado titulo={titulo} paradas={paradas} /> : <RecorridoFijo titulo={titulo} paradas={paradas} />;
}

function RecorridoFijo({ titulo, paradas }: { titulo: string; paradas: ParadaRecorrido[] }) {
  return (
    <section aria-labelledby="titulo-recorrido" className="mx-auto max-w-6xl px-6 py-20">
      <h2 id="titulo-recorrido" className="max-w-[680px] text-4xl font-semibold leading-10">
        {titulo}
      </h2>
      <ol className="mt-10 grid gap-8 md:grid-cols-2">
        {paradas.map((p, i) => (
          <li key={p.titulo}>
            <img
              src={escenaMovil(i)}
              alt=""
              width={688}
              height={384}
              loading="lazy"
              decoding="async"
              className="aspect-video w-full rounded-xl object-cover"
              style={{ backgroundColor: FONDO_ESCENA }}
            />
            <p className="etiqueta mt-4">
              {String(i + 1).padStart(2, "0")} / {String(paradas.length).padStart(2, "0")}
            </p>
            <h3 className="mt-1 text-xl font-semibold">{p.titulo}</h3>
            <p className="mt-1 text-base text-texto-2">{p.texto}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

function RecorridoAnimado({ titulo, paradas }: { titulo: string; paradas: ParadaRecorrido[] }) {
  const n = paradas.length;
  const { lista, total } = useMemo(() => segmentos(n), [n]);
  const seccion = useRef<HTMLElement>(null);
  const imagenes = useRef<(HTMLImageElement | null)[]>([]);
  const videos = useRef<(HTMLVideoElement | null)[]>([]);
  const textos = useRef<(HTMLElement | null)[]>([]);
  const barra = useRef<HTMLSpanElement>(null);
  const [actual, setActual] = useState(0);

  useEffect(() => {
    // Objetivo y posición suavizada del tiempo de cada video (0..1); el bucle persigue el objetivo.
    const objetivo = new Array(n - 1).fill(0);
    const posicion = new Array(n - 1).fill(0);
    let cuadro = 0;
    let ultimaParada = -1;

    function leer() {
      const el = seccion.current;
      if (!el) return;
      const alto = window.innerHeight;
      const y = limitar(-el.getBoundingClientRect().top / alto, 0, total);
      const seg = lista.find((s) => y >= s.inicio && y < s.fin) ?? lista[lista.length - 1]!;

      // Qué escena fija queda debajo: la de la parada o, en un tramo, la del extremo más cercano.
      let fija = seg.i;
      if (seg.tipo === "tramo") fija = (y - seg.inicio) / (seg.fin - seg.inicio) < 0.5 ? seg.i : seg.i + 1;
      imagenes.current.forEach((img, k) => img && (img.style.opacity = k === fija ? "1" : "0"));

      videos.current.forEach((v, k) => {
        if (!v) return;
        const s = lista.find((x) => x.tipo === "tramo" && x.i === k)!;
        const local = limitar((y - s.inicio) / (s.fin - s.inicio));
        objetivo[k] = local;
        const dentro = seg.tipo === "tramo" && seg.i === k;
        v.style.opacity = dentro ? String(suave(Math.min(local / FUNDIDO, (1 - local) / FUNDIDO))) : "0";
      });

      // Cada texto se enciende cerca de su parada y se apaga en el tramo siguiente.
      textos.current.forEach((t, k) => {
        if (!t) return;
        const s = lista.find((x) => x.tipo === "parada" && x.i === k)!;
        const centro = (s.inicio + s.fin) / 2;
        const ancho = k === 0 || k === n - 1 ? PESO_PARADA * 0.5 + PESO_TRAMO * 0.45 : PESO_PARADA * 0.5 + PESO_TRAMO * 0.4;
        let d = Math.abs(y - centro) / ancho;
        if ((k === 0 && y < centro) || (k === n - 1 && y > centro)) d = 0;
        const op = suave(1 - d);
        t.style.opacity = String(op);
        t.style.transform = `translateY(${((centro - y) * 3).toFixed(2)}vh)`;
        t.style.visibility = op < 0.01 ? "hidden" : "visible";
      });

      const cercana = seg.tipo === "parada" ? seg.i : fija;
      if (cercana !== ultimaParada) {
        ultimaParada = cercana;
        setActual(cercana);
      }
      if (barra.current) barra.current.style.transform = `scaleX(${(y / total).toFixed(4)})`;
    }

    function bucle() {
      videos.current.forEach((v, k) => {
        if (!v || v.readyState < 1 || v.seeking) return;
        if (Math.abs(posicion[k] - objetivo[k]) < 0.0005) return;
        posicion[k] += (objetivo[k] - posicion[k]) * 0.2;
        const t = limitar(posicion[k], 0, 0.999) * (v.duration || 1);
        if (Math.abs(v.currentTime - t) > 0.01) v.currentTime = t;
      });
      cuadro = requestAnimationFrame(bucle);
    }

    let pendiente = false;
    const alScroll = () => {
      if (pendiente) return;
      pendiente = true;
      requestAnimationFrame(() => {
        pendiente = false;
        leer();
      });
    };
    window.addEventListener("scroll", alScroll, { passive: true });
    window.addEventListener("resize", alScroll);
    leer();
    cuadro = requestAnimationFrame(bucle);
    return () => {
      window.removeEventListener("scroll", alScroll);
      window.removeEventListener("resize", alScroll);
      cancelAnimationFrame(cuadro);
    };
  }, [lista, total, n, paradas.length]);

  const irA = (k: number) => {
    const el = seccion.current;
    const s = lista.find((x) => x.tipo === "parada" && x.i === k);
    if (!el || !s) return;
    const top = el.getBoundingClientRect().top + window.scrollY + ((s.inicio + s.fin) / 2) * window.innerHeight;
    window.scrollTo({ top, behavior: "smooth" });
  };

  return (
    <section ref={seccion} aria-labelledby="titulo-recorrido" className="relative" style={{ height: `${(total + 1) * 100}vh` }}>
      <div className="sticky top-0 h-screen overflow-hidden" style={{ backgroundColor: FONDO_ESCENA }}>
        {paradas.map((_, i) => (
          <img
            key={i}
            ref={(el) => {
              imagenes.current[i] = el;
            }}
            src={escena(i)}
            alt=""
            decoding="async"
            className={ESCENARIO}
            style={{ opacity: i === 0 ? 1 : 0 }}
          />
        ))}
        {paradas.slice(1).map((_, i) => (
          <video
            key={i}
            ref={(el) => {
              videos.current[i] = el;
            }}
            src={tramo(i)}
            muted
            playsInline
            preload="auto"
            aria-hidden
            tabIndex={-1}
            className={ESCENARIO}
            style={{ opacity: 0 }}
          />
        ))}

        {/* Velo a la izquierda para que el texto se lea sobre la escena. */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-y-0 left-0 w-[min(56vw,760px)]"
          style={{ background: `linear-gradient(90deg, ${FONDO_ESCENA} 0%, ${FONDO_ESCENA}d9 38%, ${FONDO_ESCENA}66 66%, transparent 100%)` }}
        />
        <div aria-hidden className="absolute inset-x-0 top-0 h-0.5 bg-[#d3dce5]">
          <span ref={barra} className="block h-full origin-left bg-[#0e7c86]" style={{ transform: "scaleX(0)" }} />
        </div>

        <div className="relative mx-auto h-full max-w-6xl px-6 text-[#14212e]">
          <h2 id="titulo-recorrido" className="absolute top-24 max-w-md text-sm font-medium text-[#4a5a6a]">
            {titulo}
          </h2>
          <ol>
            {paradas.map((p, i) => (
              <li
                key={p.titulo}
                ref={(el) => {
                  textos.current[i] = el;
                }}
                className="absolute top-1/2 -mt-16 max-w-md will-change-[opacity,transform]"
                style={{ opacity: i === 0 ? 1 : 0 }}
              >
                <p className="font-mono text-xs tracking-widest text-[#4a5a6a]">
                  {String(i + 1).padStart(2, "0")} / {String(n).padStart(2, "0")}
                </p>
                <h3 className="mt-3 text-5xl font-semibold leading-none">{p.titulo}</h3>
                <p className="mt-4 max-w-sm text-lg text-[#33465a]">{p.texto}</p>
              </li>
            ))}
          </ol>
        </div>

        <nav aria-label="Escenas del recorrido" className="absolute right-6 top-1/2 flex -translate-y-1/2 flex-col gap-3">
          {paradas.map((p, i) => (
            <button
              key={p.titulo}
              type="button"
              onClick={() => irA(i)}
              aria-label={`Ir a: ${p.titulo}`}
              aria-current={i === actual ? "step" : undefined}
              className="group grid size-6 place-items-center rounded-full"
            >
              <span
                className={cn(
                  "block size-2 rounded-full transition-[transform,background-color] duration-300 ease-[var(--ease-salida)]",
                  i === actual ? "scale-150 bg-[#0e7c86]" : "bg-[#0b2e4a]/25 group-hover:bg-[#0b2e4a]/60",
                )}
              />
            </button>
          ))}
        </nav>
      </div>
    </section>
  );
}
