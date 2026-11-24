import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check, FileText, List, Plus, ShieldCheck, X } from "../iconos";
import { Marca } from "../componentes/Marca";
import { boton } from "../componentes/ui/Boton";
import { Insignia } from "../componentes/ui/Insignia";
import { RecorridoHospital, type ParadaRecorrido } from "../componentes/RecorridoHospital";
import { cn } from "../lib/cn";
import { CONTACTO_PRIVACIDAD } from "../lib/legal";

export interface ContenidoLanding {
  titular: string;
  subtitular: string;
  cta: { texto: string; a: string };
  apoyo: string;
  pregunta: string;
  respuesta: string;
  /** Fuente que muestra el ejemplo: de dónde sale la respuesta. */
  fuente: { documento: string; extracto: string };
  lema: string;
  /** Recorrido animado por el hospital: una parada por escena, en el orden de las imágenes. */
  recorrido: { titulo: string; paradas: ParadaRecorrido[] };
  pasos: { titulo: string; texto: string }[];
  beneficios: { titulo: string; texto: string }[];
  preguntas: { p: string; r: string }[];
  riesgo: { titulo: string; texto: string };
  cierre: string;
  alterna: { texto: string; a: string };
}

/** Revela un texto palabra por palabra al entrar en pantalla: del tono atenuado al color pleno, una sola vez. */
function LemaPorPalabras({ texto }: { texto: string }) {
  const palabras = texto.split(" ");
  const refs = useRef<(HTMLSpanElement | null)[]>([]);
  const [activas, setActivas] = useState(() => new Set<number>());
  const reducido = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    if (reducido || typeof IntersectionObserver === "undefined") return;
    const observador = new IntersectionObserver(
      (entradas) => {
        entradas.forEach((e) => {
          if (e.isIntersecting) {
            const i = Number((e.target as HTMLElement).dataset.i);
            setActivas((previas) => new Set(previas).add(i));
            observador.unobserve(e.target);
          }
        });
      },
      { rootMargin: "0px 0px -30% 0px" },
    );
    refs.current.forEach((el) => el && observador.observe(el));
    return () => observador.disconnect();
  }, [reducido]);

  return (
    <p className="text-4xl font-semibold leading-10 sm:text-5xl sm:leading-none">
      {palabras.map((w, i) => (
        <span
          key={i}
          ref={(el) => {
            refs.current[i] = el;
          }}
          data-i={i}
          className={cn(
            "transition-colors duration-500 ease-[var(--ease-salida)]",
            reducido || activas.has(i) ? "text-texto" : "text-texto/30",
          )}
          style={{ transitionDelay: reducido ? undefined : `${Math.min(i * 25, 300)}ms` }}
        >
          {w}{" "}
        </span>
      ))}
    </p>
  );
}

/** Aparece una sola vez al entrar en pantalla: sube 32 px y se hace visible. */
function Revelar({ children, className }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const reducido = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reducido || typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const o = new IntersectionObserver(
      ([e]) => {
        if (e?.isIntersecting) {
          setVisible(true);
          o.disconnect();
        }
      },
      { rootMargin: "0px 0px -10% 0px" },
    );
    if (ref.current) o.observe(ref.current);
    return () => o.disconnect();
  }, []);
  return (
    <div
      ref={ref}
      className={cn(
        "transition-[opacity,transform] duration-700 ease-[var(--ease-salida)]",
        visible ? "translate-y-0 opacity-100" : "translate-y-8 opacity-0",
        className,
      )}
    >
      {children}
    </div>
  );
}

const ENLACES = [
  ["#como-funciona", "Cómo funciona"],
  ["#seguridad", "Seguridad"],
  ["#preguntas", "Preguntas"],
] as const;

function Navegacion({ c }: { c: ContenidoLanding }) {
  const [abierto, setAbierto] = useState(false);
  return (
    <>
      <header className="fixed inset-x-0 top-4 z-40 flex justify-center px-4">
        <div className="flex w-full max-w-3xl items-center gap-3 rounded-xl border border-borde bg-panel/80 p-2 pl-4 backdrop-blur-md">
          <Link to="/" aria-label="MedTender, inicio" className="shrink-0">
            <Marca />
          </Link>
          <nav className="ml-auto hidden items-center gap-1 md:flex" aria-label="Secciones de la página">
            {ENLACES.map(([a, t]) => (
              <a key={a} href={a} className="rounded-lg px-3 py-2 text-sm font-medium text-texto-2 transition-colors duration-300 hover:bg-panel-2 hover:text-texto">
                {t}
              </a>
            ))}
            <Link to={c.alterna.a} className="rounded-lg px-3 py-2 text-sm font-medium text-texto-2 transition-colors duration-300 hover:bg-panel-2 hover:text-texto">
              {c.alterna.texto}
            </Link>
          </nav>
          <Link to="/ingreso" className={cn(boton({ variante: "secundario", tamano: "sm" }), "ml-auto md:ml-2")}>
            Ingresar
          </Link>
          <button
            type="button"
            className="grid size-8 place-items-center rounded-lg text-texto transition-colors duration-300 hover:bg-panel-2 md:hidden"
            aria-label={abierto ? "Cerrar menú" : "Abrir menú"}
            aria-expanded={abierto}
            onClick={() => setAbierto((v) => !v)}
          >
            <span className="relative block size-4">
              <List className={cn("absolute inset-0 size-4 transition-[opacity,transform] duration-500 ease-[var(--ease-salida)]", abierto ? "rotate-90 opacity-0" : "opacity-100")} aria-hidden />
              <X className={cn("absolute inset-0 size-4 transition-[opacity,transform] duration-500 ease-[var(--ease-salida)]", abierto ? "opacity-100" : "-rotate-90 opacity-0")} aria-hidden />
            </span>
          </button>
        </div>
      </header>
      {abierto && (
        <div className="fixed inset-0 z-30 bg-fondo/95 px-6 pt-24 backdrop-blur-xl md:hidden" role="dialog" aria-label="Menú">
          <nav className="flex flex-col gap-2" aria-label="Secciones de la página">
            {[...ENLACES.map(([a, t]) => [a, t, false] as const), [c.alterna.a, c.alterna.texto, true] as const].map(([a, t, ruta], i) => {
              const clase = "block rounded-xl px-3 py-3 text-2xl font-semibold text-texto animate-[aparecer_500ms_var(--ease-salida)_both]";
              const estilo = { animationDelay: `${Math.min(i * 60, 400)}ms` };
              return ruta ? (
                <Link key={a} to={a} className={clase} style={estilo} onClick={() => setAbierto(false)}>
                  {t}
                </Link>
              ) : (
                <a key={a} href={a} className={clase} style={estilo} onClick={() => setAbierto(false)}>
                  {t}
                </a>
              );
            })}
          </nav>
        </div>
      )}
    </>
  );
}

/** Ejemplo ilustrativo de una respuesta con su cita, dibujado en código con datos de demostración. */
function MuestraRespuesta({ c }: { c: ContenidoLanding }) {
  return (
    <figure className="panel w-full max-w-xl p-4" aria-label="Ejemplo ilustrativo de una respuesta con su cita">
      <figcaption className="mb-3 flex items-center justify-between gap-3">
        <span className="text-xs font-medium text-texto-3">Ejemplo ilustrativo, datos de demostración</span>
        <Insignia tono="neutro">Consulta</Insignia>
      </figcaption>
      <p className="rounded-lg bg-panel-2 px-3 py-3 text-sm font-medium">{c.pregunta}</p>
      <p className="mt-3 px-1 text-base">
        {c.respuesta}
        <span className="ml-1 inline-grid h-5 min-w-5 place-items-center rounded-md bg-cita px-1 text-xs font-semibold text-cita-tx">1</span>
      </p>
      <div className="mt-4 rounded-lg border border-borde p-3">
        <p className="flex items-center gap-2 text-xs font-medium text-texto-2">
          <span className="grid h-5 min-w-5 place-items-center rounded-md bg-cita px-1 font-semibold text-cita-tx">1</span>
          <FileText className="size-4" aria-hidden />
          {c.fuente.documento}
        </p>
        <p className="mt-2 text-sm">
          <span className="resaltado">«{c.fuente.extracto}»</span>
        </p>
        <p className="etiqueta mt-2">sha256 6fd7 08299d… · fuente verificada</p>
      </div>
    </figure>
  );
}

export function Landing({ c }: { c: ContenidoLanding }) {
  return (
    <div className="min-h-screen bg-fondo">
      <a href="#principal" className="sr-only rounded-lg bg-primario px-4 py-2 text-sm font-semibold text-primario-tx focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50">
        Saltar al contenido
      </a>
      <Navegacion c={c} />

      <main id="principal">
        {/* Hero */}
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-6 pb-20 pt-24 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div>
            <h1 className="max-w-[680px] bg-linear-to-r from-[#000000] to-[#666666] bg-clip-text text-5xl font-semibold leading-none text-transparent dark:from-white dark:to-[#9b9b9b] sm:text-6xl">
              {c.titular}
            </h1>
            <p className="mt-6 max-w-[680px] text-lg text-texto-2">{c.subtitular}</p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <Link to={c.cta.a} className={boton({ variante: "primario", tamano: "lg" })}>
                {c.cta.texto}
                <ArrowRight className="size-5" aria-hidden />
              </Link>
            </div>
            <p className="mt-6 flex max-w-[680px] items-start gap-2 text-sm text-texto-2">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primario" aria-hidden />
              {c.apoyo}
            </p>
          </div>
          <Revelar className="flex justify-center lg:justify-end">
            <MuestraRespuesta c={c} />
          </Revelar>
        </section>

        {/* Recorrido por el hospital, movido por el scroll */}
        <RecorridoHospital titulo={c.recorrido.titulo} paradas={c.recorrido.paradas} />

        {/* Lema */}
        <section className="mx-auto max-w-6xl px-6 py-24" aria-label="Lo que prometemos">
          <div className="max-w-3xl">
            <LemaPorPalabras texto={c.lema} />
          </div>
        </section>

        {/* Cómo funciona */}
        <section id="como-funciona" className="mx-auto max-w-6xl scroll-mt-24 px-6 py-20">
          <Revelar>
            <h2 className="max-w-[680px] text-4xl font-semibold leading-10">Cómo funciona</h2>
            <ol className="mt-10 grid gap-8 md:grid-cols-3">
              {c.pasos.map((p, i) => (
                <li key={p.titulo} className="panel p-6">
                  <span className="grid size-8 place-items-center rounded-lg bg-marino text-sm font-semibold text-white" aria-hidden>
                    {i + 1}
                  </span>
                  <h3 className="mt-4 text-xl font-semibold">{p.titulo}</h3>
                  <p className="mt-2 text-base text-texto-2">{p.texto}</p>
                </li>
              ))}
            </ol>
          </Revelar>
        </section>

        {/* Beneficios */}
        <section className="mx-auto max-w-6xl px-6 py-20" aria-label="Beneficios">
          <Revelar>
            <h2 className="max-w-[680px] text-4xl font-semibold leading-10">Lo que cambia cuando cada respuesta trae su fuente</h2>
            <dl className="mt-10 grid gap-x-12 gap-y-8 md:grid-cols-2">
              {c.beneficios.map((b) => (
                <div key={b.titulo} className="flex gap-4 border-t border-borde pt-4">
                  <Check className="mt-1 size-5 shrink-0 text-primario" aria-hidden />
                  <div>
                    <dt className="text-lg font-semibold">{b.titulo}</dt>
                    <dd className="mt-1 text-base text-texto-2">{b.texto}</dd>
                  </div>
                </div>
              ))}
            </dl>
          </Revelar>
        </section>

        {/* Seguridad y reversión del riesgo */}
        <section id="seguridad" className="mx-auto max-w-6xl scroll-mt-24 px-6 py-20">
          <Revelar>
            <div className="panel flex flex-col gap-4 bg-marino p-8 text-white md:flex-row md:items-center md:justify-between">
              <div className="max-w-[680px]">
                <h2 className="text-3xl font-semibold">{c.riesgo.titulo}</h2>
                <p className="mt-2 text-base text-white/80">{c.riesgo.texto}</p>
              </div>
              <Link to={c.cta.a} className={cn(boton({ variante: "secundario", tamano: "lg" }), "shrink-0 border-transparent")}>
                {c.cta.texto}
              </Link>
            </div>
          </Revelar>
        </section>

        {/* Preguntas */}
        <section id="preguntas" className="mx-auto max-w-3xl scroll-mt-24 px-6 py-20">
          <Revelar>
            <h2 className="text-4xl font-semibold leading-10">Preguntas frecuentes</h2>
            <div className="mt-8 divide-y divide-borde border-y border-borde">
              {c.preguntas.map((q) => (
                <details key={q.p} className="group py-4">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-lg font-medium transition-colors duration-300 hover:text-primario">
                    {q.p}
                    <Plus className="size-5 shrink-0 text-texto-3 transition-transform duration-500 ease-[var(--ease-salida)] group-open:rotate-45" aria-hidden />
                  </summary>
                  <p className="mt-3 text-base text-texto-2">{q.r}</p>
                </details>
              ))}
            </div>
          </Revelar>
        </section>

        {/* Llamado final, el mismo del inicio */}
        <section className="mx-auto max-w-6xl px-6 pb-24 pt-12 text-center">
          <Revelar>
            <h2 className="mx-auto max-w-[680px] text-4xl font-semibold leading-10">{c.cierre}</h2>
            <div className="mt-8">
              <Link to={c.cta.a} className={boton({ variante: "primario", tamano: "lg" })}>
                {c.cta.texto}
                <ArrowRight className="size-5" aria-hidden />
              </Link>
            </div>
          </Revelar>
        </section>
      </main>

      <footer className="border-t border-borde px-6 py-8">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 text-sm text-texto-2">
          <Marca />
          <nav className="flex flex-wrap items-center gap-6" aria-label="Información legal">
            <Link to="/privacidad" className="transition-colors duration-300 hover:text-texto">
              Privacidad
            </Link>
            <Link to="/terminos" className="transition-colors duration-300 hover:text-texto">
              Términos
            </Link>
            {CONTACTO_PRIVACIDAD && (
              <a href={`mailto:${CONTACTO_PRIVACIDAD}`} className="transition-colors duration-300 hover:text-texto">
                Contacto
              </a>
            )}
          </nav>
          <p className="text-xs text-texto-3">MedTender está en pruebas cerradas. No sustituye a un profesional de la salud.</p>
        </div>
      </footer>
    </div>
  );
}
