import { ArrowRight, BadgeCheck, Building2, Lock, ScrollText, Trash2 } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Montanas } from "../arte/Montanas";
import { AvisoPurga, Grafito, VentanaConsulta, VisorDocumento, ZonaCarga } from "../arte/TarjetasUI";
import { Marca } from "../componentes/Marca";
import { boton } from "../componentes/ui/Boton";
import { cn } from "../lib/cn";

/** Aparece al entrar en pantalla (una sola vez), con la misma curva que el resto de la interfaz. */
function Revelar({ children, retraso = 0, className }: { children: ReactNode; retraso?: number; className?: string }) {
  const quieto = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={quieto ? false : { opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.75, delay: retraso, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}

export function PaginaBienvenida() {
  return (
    <div className="relative overflow-x-clip bg-sala">
      <Navegacion />
      <Heroe />
      <PreguntaYComprueba />
      <ComoFunciona />
      <Capacidades />
      <Seguridad />
      <Voces />
      <Cierre />
    </div>
  );
}

/* -------------------------------------------------------------- navegación */

/** Transparente sobre el héroe; al bajar se vuelve un fondo oscuro esmerilado. */
function Navegacion() {
  const [fondo, setFondo] = useState(false);
  useEffect(() => {
    const alBajar = () => setFondo(window.scrollY > 24);
    alBajar();
    window.addEventListener("scroll", alBajar, { passive: true });
    return () => window.removeEventListener("scroll", alBajar);
  }, []);
  const enlace = "rounded-full px-5 py-2 text-base text-tx transition-colors hover:bg-ink/10";
  return (
    <header className={cn("fixed inset-x-0 top-0 z-40 transition-[background-color,backdrop-filter] duration-300", fondo && "bg-sala/75 backdrop-blur-xl")}>
      <div className="mx-auto flex max-w-[1200px] items-center justify-between px-5 py-4 sm:px-8">
        <Link to="/" aria-label="MedTender, inicio">
          <Marca />
        </Link>
        <nav className="hidden items-center md:flex" aria-label="Secciones">
          <a href="#como-funciona" className={enlace}>Cómo funciona</a>
          <a href="#capacidades" className={enlace}>Capacidades</a>
          <a href="#seguridad" className={enlace}>Seguridad</a>
        </nav>
        <Link to="/ingreso" className={boton({ variante: "secundario", tamano: "md" })}>
          Ingresar
        </Link>
      </div>
    </header>
  );
}

/* ------------------------------------------------------------------ héroe */

function Heroe() {
  return (
    <section className="relative isolate grid min-h-[100svh] place-items-center overflow-hidden px-5 pb-24 pt-32">
      <Montanas />
      <div className="mx-auto max-w-[64rem] text-center">
        <Revelar>
          <h1 className="text-[clamp(2.2rem,5.2vw,4.06rem)]">
            <span className="block">Pregunta a tu expediente.</span>
            <span className="block">El PDF no se queda.</span>
          </h1>
        </Revelar>
        <Revelar retraso={0.1}>
          <p className="mx-auto mt-6 max-w-[34rem] text-[1.125rem] font-[480] leading-[1.4] text-tx">
            Audita licitaciones médicas en segundos: cada respuesta llega con el extracto literal, la página y la huella del archivo.
            Tus originales se indexan, se eliminan del servidor y se abren solo desde tu equipo.
          </p>
        </Revelar>
        <Revelar retraso={0.2} className="mt-10 flex flex-wrap items-center justify-center gap-4">
          <Link to="/ingreso" className={boton({ variante: "primario", tamano: "lg" })}>
            Empezar
            <ArrowRight className="size-[1.1rem]" aria-hidden />
          </Link>
          <a href="#como-funciona" className={boton({ variante: "secundario", tamano: "lg" })}>
            Ver cómo funciona
          </a>
        </Revelar>
      </div>
    </section>
  );
}

/* ------------------------------------------------- pregunta y comprueba */

function Titular({ children, className }: { children: ReactNode; className?: string }) {
  return <h2 className={cn("text-[clamp(1.9rem,3.4vw,2.6rem)]", className)}>{children}</h2>;
}

function PreguntaYComprueba() {
  return (
    <section className="mx-auto max-w-[1200px] px-5 py-[72px] sm:px-8 sm:py-28">
      <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
        <Revelar>
          <Titular>Cada respuesta llega con su prueba.</Titular>
          <p className="mt-5 max-w-[30rem] text-[1.125rem] leading-[1.4] text-tx-2">
            Cada respuesta cita documento, página y extracto literal. Para verificarla, abre el original desde tu carpeta: comparamos
            su huella SHA-256 sin que el archivo salga de tu equipo.
          </p>
          <AvisoPurga className="mt-8" />
        </Revelar>
        <Revelar retraso={0.1} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
          <VentanaConsulta />
          <VisorDocumento className="sm:mt-10 lg:mt-0 xl:mt-10" />
        </Revelar>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------- cómo funciona */

function Fila({ ok = true, children }: { ok?: boolean; children: ReactNode }) {
  return (
    <li className="flex items-center gap-3 py-1.5 text-[0.9rem]">
      <span className={cn("grid size-[1.1rem] place-items-center rounded-full", ok ? "bg-ok text-sala" : "bg-obsidiana text-tx-3")}>
        <BadgeCheck className="size-3" aria-hidden />
      </span>
      {children}
    </li>
  );
}

const PASOS: { titulo: string; texto: string; ilustra: ReactNode }[] = [
  {
    titulo: "Sube el pliego",
    texto: "Arrastra los PDF del expediente. Revisamos que sean válidos, sin virus y sin contraseña de apertura antes de seguir.",
    ilustra: <ZonaCarga />,
  },
  {
    titulo: "Lo indexamos y lo borramos",
    texto:
      "Extraemos el texto (con OCR solo donde hace falta), lo partimos en fragmentos y lo convertimos en vectores. Con el índice verificado, el PDF se elimina y queda un acta de purga.",
    ilustra: (
      <ul className="rounded-xl bg-obsidiana px-4 py-3">
        <Fila>Texto y OCR selectivo</Fila>
        <Fila>Fragmentos y vectores</Fila>
        <Fila>Índice verificado</Fila>
        <Fila>PDF eliminado</Fila>
      </ul>
    ),
  },
  {
    titulo: "Pregunta y comprueba",
    texto: "Obtienes la respuesta con la cita exacta y la huella del archivo. Si no hay evidencia, te lo dice en lugar de conjeturar.",
    ilustra: (
      <div className="rounded-xl bg-obsidiana p-4 text-[0.88rem] leading-snug">
        <span className="inline-flex items-center gap-1.5 text-[0.7rem] text-ok">
          <BadgeCheck className="size-3.5" aria-hidden />
          Fuente verificada
        </span>
        <p className="mt-2">«La garantía de cumplimiento tendrá una vigencia de doce (12) meses…»</p>
        <p className="mt-2 font-mono text-[0.66rem] text-tx-3">Pliego · pág. 14 · sha256 ✓</p>
      </div>
    ),
  },
];

function ComoFunciona() {
  return (
    <section id="como-funciona" className="mx-auto max-w-[1200px] scroll-mt-16 px-5 py-[72px] sm:px-8">
      <Revelar className="max-w-2xl">
        <Titular>Tres pasos, y tu archivo nunca se queda.</Titular>
      </Revelar>
      <ol className="mt-14 grid gap-3 lg:grid-cols-3">
        {PASOS.map((p, i) => (
          <li key={p.titulo}>
            <Revelar retraso={i * 0.08} className="h-full">
              <Grafito className="flex h-full flex-col p-8">
                <div className="mb-8">{p.ilustra}</div>
                <h3 className="text-[1.5rem]">{p.titulo}</h3>
                <p className="mt-3 leading-relaxed text-tx-2">{p.texto}</p>
              </Grafito>
            </Revelar>
          </li>
        ))}
      </ol>
    </section>
  );
}

/* ------------------------------------------------------------- capacidades */

function Capacidades() {
  return (
    <section id="capacidades" className="mx-auto max-w-[1200px] scroll-mt-16 px-5 py-[72px] sm:px-8 sm:py-28">
      <Revelar className="max-w-2xl">
        <Titular>Hecho para quien firma lo que audita.</Titular>
        <p className="mt-5 text-[1.125rem] leading-[1.4] text-tx-2">
          Una herramienta de trabajo diario: rápida de escanear, honesta cuando no sabe, y con la fuente siempre a un clic.
        </p>
      </Revelar>

      <div className="mt-14 grid gap-3 lg:grid-cols-2">
        <Revelar>
          <Grafito className="h-full p-8">
            <h3 className="text-[1.5rem]">Las adendas pesan más que el pliego base</h3>
            <p className="mt-3 text-tx-2">
              El modelo solo elige qué fragmentos usar; el extracto que ves es el texto real del documento. Cuando una adenda
              modifica un punto, la respuesta lo señala.
            </p>
            <div className="mt-8 space-y-3">
              <div className="rounded-xl bg-obsidiana p-4">
                <span className="inline-flex items-center gap-1.5 rounded-full border border-ambar/45 px-3 py-0.5 text-[0.72rem] text-ambar">
                  <ScrollText className="size-3.5" aria-hidden />
                  Adenda N° 2 modifica este punto
                </span>
                <p className="mt-3 leading-snug">«El plazo de entrega será de quince (15) días calendario.»</p>
                <p className="etiqueta mt-2.5">Adenda 2 · pág. 1 · ejemplo</p>
              </div>
              <div className="rounded-xl bg-obsidiana p-4 text-[0.9rem] leading-relaxed text-tx-2">
                <span className="text-coral">Verificar original.</span> Sello o firma detectados en la página: conviene mirar el PDF y no
                fiarse solo del texto extraído.
              </div>
            </div>
          </Grafito>
        </Revelar>
        <Revelar retraso={0.08}>
          <Grafito className="flex h-full flex-col p-8">
            <h3 className="text-[1.5rem]">Prefiere callar a inventar</h3>
            <p className="mt-3 text-tx-2">
              Sin soporte documental, la respuesta es una abstención explícita. Nunca una conjetura con buena redacción.
            </p>
            <div className="mt-8 rounded-xl bg-obsidiana p-4 lg:mt-auto">
              <p className="text-[0.84rem] text-ambar">Sin evidencia suficiente</p>
              <p className="mt-1.5 text-[0.9rem] leading-relaxed text-tx-2">
                No encontré en los documentos indexados nada que responda esta pregunta.
              </p>
            </div>
          </Grafito>
        </Revelar>
      </div>

      <div className="mt-14 grid gap-x-10 gap-y-9 sm:grid-cols-3">
        {[
          ["Visor local desacoplado", "Vincula una carpeta de tu equipo. El original se abre en la página citada y se compara su SHA-256. No se sube nada. Chrome y Edge."],
          ["El proceso, a la vista", "Antivirus y validación, texto y OCR selectivo, fragmentos y vectores, PDF eliminado: cada estado visible, con lenguaje claro."],
          ["Cada organización, aparte", "Aislamiento por organización, permisos por expediente y un registro de auditoría que nadie puede reescribir."],
        ].map(([t, d], i) => (
          <Revelar key={t} retraso={i * 0.06}>
            <h3 className="text-[1.15rem]">{t}</h3>
            <p className="mt-2 leading-relaxed text-tx-2">{d}</p>
          </Revelar>
        ))}
      </div>
    </section>
  );
}

/* --------------------------------------------------------------- seguridad */

const FILAS_ACTA: [string, string][] = [
  ["Documento", "Pliego_E2E.pdf"],
  ["Fragmentos indexados", "128 de 128"],
  ["Vectores verificados", "128 de 128"],
  ["Huella SHA-256", "9f3a…c41e"],
  ["Estado del original", "Eliminado"],
];

function Seguridad() {
  return (
    <section id="seguridad" className="mx-auto max-w-[1200px] scroll-mt-16 px-5 py-[72px] sm:px-8">
      <div className="grid items-start gap-12 lg:grid-cols-2 lg:gap-16">
        <div>
          <Revelar>
            <Titular>Tus documentos son confidenciales. El diseño también.</Titular>
          </Revelar>
          <ul className="mt-10 space-y-7">
            {[
              [Trash2, "El PDF se elimina", "Tras indexar y verificar que todos los fragmentos tienen su vector, el archivo se borra y queda un acta con su huella."],
              [Building2, "Solo lo tuyo", "Cada consulta se filtra por organización y expediente. Lo ajeno responde «no encontrado»."],
              [ScrollText, "Auditoría de solo anexado", "Accesos, denegaciones y consultas quedan registrados sin guardar el texto de tus preguntas."],
              [Lock, "Conexión cifrada", "Todo viaja por HTTPS, con una política de seguridad estricta y sin servicios de terceros en la página."],
            ].map(([Icono, titulo, texto], i) => {
              const I = Icono as typeof Trash2;
              return (
                <li key={String(titulo)}>
                  <Revelar retraso={i * 0.05} className="flex gap-4">
                    <I className="mt-1 size-5 shrink-0 text-tx-2" strokeWidth={1.5} aria-hidden />
                    <div>
                      <h3 className="text-[1.1rem]">{String(titulo)}</h3>
                      <p className="mt-1 leading-relaxed text-tx-2">{String(texto)}</p>
                    </div>
                  </Revelar>
                </li>
              );
            })}
          </ul>
        </div>

        <Revelar retraso={0.1}>
          <Grafito className="p-8">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[0.78rem] text-tx-3">Acta de purga</p>
                <p className="mt-1 font-display text-[1.6rem] font-[480] leading-none [font-stretch:112%]">PDF eliminado</p>
              </div>
              <span className="etiqueta rounded-full border border-ink/30 px-3 py-0.5">ejemplo</span>
            </div>
            <dl className="mt-6 text-[0.88rem]">
              {FILAS_ACTA.map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between gap-4 border-t border-ink/10 py-3">
                  <dt className="text-tx-2">{k}</dt>
                  <dd className="font-mono">{v}</dd>
                </div>
              ))}
            </dl>
          </Grafito>
        </Revelar>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------- voces */

const VOCES = [
  {
    texto: "Antes me tomaba una tarde cruzar el pliego con tres adendas. Ahora pregunto, veo la cita y abro el original para confirmar.",
    nombre: "Camila R.",
    cargo: "Auditora médica · hospital de ejemplo",
  },
  {
    texto: "Que el PDF no se quede en el servidor fue lo que convenció a nuestro comité de seguridad.",
    nombre: "Andrés M.",
    cargo: "Ingeniero biomédico · entidad de ejemplo",
  },
  {
    texto: "Cuando no hay soporte en los documentos, lo dice. Eso, para un abogado, vale oro.",
    nombre: "Lucía P.",
    cargo: "Abogada de contratación · aseguradora de ejemplo",
  },
];

function Voces() {
  return (
    <section className="mx-auto max-w-[1200px] px-5 py-[72px] sm:px-8 sm:py-28" aria-labelledby="titulo-voces">
      <Revelar className="flex flex-wrap items-end justify-between gap-4">
        <Titular>
          <span id="titulo-voces">Lo que dirían quienes lo usan.</span>
        </Titular>
        <p className="rounded-full border border-ambar/45 px-4 py-1 text-[0.8rem] text-ambar">Testimonios de ejemplo, no son de clientes reales</p>
      </Revelar>
      <div className="mt-12 grid gap-3 lg:grid-cols-3">
        {VOCES.map((v, i) => (
          <Revelar key={v.nombre} retraso={i * 0.08}>
            <Grafito className="flex h-full flex-col justify-between p-8">
              <blockquote className="text-[1.15rem] leading-snug">«{v.texto}»</blockquote>
              <figcaption className="mt-8 text-[0.9rem] leading-tight">
                <span className="block">{v.nombre}</span>
                <span className="mt-1 block text-tx-3">{v.cargo}</span>
              </figcaption>
            </Grafito>
          </Revelar>
        ))}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ cierre */

function Cierre() {
  return (
    <section className="relative isolate overflow-hidden px-5 pt-32">
      <Montanas />
      <Revelar className="mx-auto max-w-3xl text-center">
        <h2 className="text-[clamp(2rem,4.4vw,3.4rem)]">El próximo pliego, con la fuente a un clic.</h2>
        <p className="mx-auto mt-5 max-w-xl text-[1.125rem] text-tx">Ingresa con tu organización y crea tu primer expediente.</p>
        <div className="mt-10 flex justify-center">
          <Link to="/ingreso" className={boton({ variante: "primario", tamano: "lg" })}>
            Ingresar a MedTender
            <ArrowRight className="size-[1.1rem]" aria-hidden />
          </Link>
        </div>
      </Revelar>
      <footer className="mx-auto mt-40 flex max-w-[1200px] flex-col items-center justify-between gap-3 py-8 text-[0.75rem] text-tx-2 sm:flex-row">
        <Marca />
        <p>Los textos de las tarjetas de esta página son ejemplos ilustrativos.</p>
      </footer>
    </section>
  );
}
