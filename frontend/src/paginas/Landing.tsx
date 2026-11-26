import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check, FileText, Plus, ShieldCheck } from "../iconos";
import { Marca } from "../componentes/Marca";
import { boton } from "../componentes/ui/Boton";
import { Insignia } from "../componentes/ui/Insignia";
import { MundoHospital, type ParadaRecorrido } from "../componentes/MundoHospital";
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
      <a href="#principal" className="sr-only rounded-lg bg-primario px-4 py-2 text-sm font-semibold text-primario-tx focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[80]">
        Saltar al contenido
      </a>
      <h1 className="sr-only">{c.titular}</h1>

      {/* Portada: el hospital en miniatura a pantalla completa, recorrido con el scroll */}
      <MundoHospital
        titular={c.titular}
        subtitular={c.subtitular}
        cta={c.cta}
        alterna={c.alterna}
        paradas={c.recorrido.paradas}
      />

      {/* El resto de la página pasa por encima del escenario fijo, por debajo de la barra superior */}
      <main id="principal" className="relative z-[45] -mt-[60vh] rounded-t-2xl bg-fondo pt-16 shadow-[0_-24px_48px_-24px_rgb(11_46_74/0.18)]">
        {/* Ejemplo de respuesta con su cita */}
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-20 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div>
            <h2 className="max-w-[680px] text-4xl font-semibold leading-10">Así se ve una respuesta</h2>
            <p className="mt-4 max-w-[680px] text-lg text-texto-2">{c.subtitular}</p>
            <p className="mt-6 flex max-w-[680px] items-start gap-2 text-sm text-texto-2">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primario" aria-hidden />
              {c.apoyo}
            </p>
          </div>
          <Revelar className="flex justify-center lg:justify-end">
            <MuestraRespuesta c={c} />
          </Revelar>
        </section>

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

      <footer className="relative z-[45] border-t border-borde bg-fondo px-6 py-8">
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
