import { ArrowRight, Building2, Eye, FileText, Lock, ScrollText, Trash2 } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Negatoscopio } from "../arte/Negatoscopio";
import { Perforaciones, Pinza, PlacaPliego, type ModoPlaca } from "../arte/Placa";
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
    <div className="relative overflow-x-clip">
      <Cabecera />
      <Heroe />
      <ComoFunciona />
      <Capacidades />
      <Seguridad />
      <Voces />
      <Cierre />
    </div>
  );
}

function Cabecera() {
  const enlace = "rounded-lg px-3.5 py-2 transition-colors hover:bg-ink/[0.07] hover:text-tx";
  return (
    <header className="absolute inset-x-0 top-0 z-30">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-5 sm:px-8">
        <Link to="/" aria-label="MedTender, inicio">
          <Marca />
        </Link>
        <nav className="hidden items-center gap-1 text-sm font-semibold text-tx-2 md:flex" aria-label="Secciones">
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
    <section className="relative isolate min-h-[100svh] overflow-hidden">
      {/* La luz del panel se derrama sobre el cuarto oscuro. */}
      <div
        className="absolute inset-0 -z-10 bg-[radial-gradient(55%_75%_at_80%_58%,rgb(124_212_230/0.16),transparent_72%)]"
        aria-hidden
      />

      <div className="mx-auto grid max-w-7xl items-center gap-12 px-5 pb-20 pt-28 sm:px-8 lg:min-h-[100svh] lg:grid-cols-[minmax(0,1fr)_minmax(0,0.92fr)] lg:gap-10 lg:pb-14">
        <div className="relative z-10">
          <Revelar>
            <h1 className="text-[clamp(2.8rem,6.2vw,5.6rem)] font-extrabold leading-[0.95] tracking-[-0.035em] text-tx">
              Pregunta a tu expediente.
              <span className="relative mt-3 block w-fit text-luz-2">
                El PDF no se queda.
                <svg
                  viewBox="0 0 400 16"
                  preserveAspectRatio="none"
                  className="absolute -bottom-3 left-0 h-3.5 w-full"
                  fill="none"
                  aria-hidden
                >
                  <path
                    d="M3 10C70 3 150 13 220 7S340 9 397 4"
                    pathLength={1}
                    stroke="#ffc247"
                    strokeWidth="3.6"
                    strokeLinecap="round"
                    strokeDasharray="1"
                    className="motion-safe:animate-trazo [--largo:1] [animation-delay:700ms]"
                  />
                </svg>
              </span>
            </h1>
          </Revelar>
          <Revelar retraso={0.12}>
            <p className="mt-10 max-w-[33rem] text-[1.14rem] leading-relaxed text-tx-2">
              Audita licitaciones médicas en segundos: cada respuesta llega con el extracto literal, la página y la
              huella del archivo. Tus originales se indexan, se eliminan del servidor y se abren solo desde tu equipo.
            </p>
          </Revelar>
          <Revelar retraso={0.24} className="mt-9 flex flex-wrap items-center gap-3">
            <Link to="/ingreso" className={boton({ variante: "primario", tamano: "lg" })}>
              Empezar
              <ArrowRight className="size-[1.1rem]" aria-hidden />
            </Link>
            <a href="#como-funciona" className={boton({ variante: "secundario", tamano: "lg" })}>
              Ver cómo funciona
            </a>
          </Revelar>
          <Revelar retraso={0.36}>
            <ul className="mt-10 flex flex-wrap gap-x-6 gap-y-2.5 text-[0.88rem] font-medium text-tx-2">
              {["Pliegos y adendas", "Fichas técnicas", "Registros sanitarios", "Historias clínicas"].map((t) => (
                <li key={t} className="flex items-center gap-2">
                  <FileText className="size-4 text-hema" aria-hidden />
                  {t}
                </li>
              ))}
            </ul>
          </Revelar>
        </div>

        <Revelar retraso={0.1} className="relative lg:-mr-12 lg:ml-2">
          <Negatoscopio className="mx-auto w-full max-w-[36rem] lg:max-w-none" />
        </Revelar>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------- cómo funciona */

const PASOS: { titulo: string; texto: string; marca: string; modo: ModoPlaca }[] = [
  {
    titulo: "Sube el pliego",
    texto: "Arrastra los PDF del expediente. Revisamos que sean válidos, sin virus y sin contraseña de apertura antes de seguir.",
    marca: "validación y antivirus",
    modo: "escaneo",
  },
  {
    titulo: "Lo indexamos y lo borramos",
    texto:
      "Extraemos el texto (con OCR solo donde hace falta), lo partimos en fragmentos y lo convertimos en vectores. Con el índice verificado, el PDF se elimina y queda un acta de purga.",
    marca: "el original no queda en el servidor",
    modo: "fragmentos",
  },
  {
    titulo: "Pregunta y comprueba",
    texto:
      "Cada respuesta cita documento, página y extracto literal. Para verificarla, abre el original desde tu carpeta: comparamos su huella SHA-256 sin que el archivo salga de tu equipo.",
    marca: "cita verificable",
    modo: "hallazgo",
  },
];

/** Una placa colgada de sus pinzas sobre el panel de luz. */
function PlacaColgada({ modo }: { modo: ModoPlaca }) {
  return (
    <div className="relative mx-auto w-full max-w-[15.5rem] pt-3">
      <Pinza className="left-[18%] !top-0 !h-6 !w-12" />
      <Pinza className="right-[18%] !top-0 !h-6 !w-12" />
      <div className="aspect-[4/5] overflow-hidden rounded-[3px] shadow-[0_22px_26px_-16px_rgb(10_19_34/0.75)]">
        <PlacaPliego modo={modo} />
      </div>
    </div>
  );
}

function ComoFunciona() {
  return (
    <section id="como-funciona" className="panel-luz relative scroll-mt-8 py-24 text-[#0a1322] sm:py-32">
      <div className="mx-auto max-w-7xl px-5 sm:px-8">
        <Revelar className="max-w-3xl">
          <h2 className="text-[clamp(2.1rem,4.6vw,3.8rem)] font-extrabold leading-[1] text-[#0a1322]">
            Tres pasos, y tu archivo nunca se queda.
          </h2>
        </Revelar>

        <ol className="mt-16 grid gap-16 lg:grid-cols-3 lg:gap-10">
          {PASOS.map((p, i) => (
            <li key={p.titulo}>
              <Revelar retraso={i * 0.12}>
                <PlacaColgada modo={p.modo} />
                <div className="mt-9">
                  <h3 className="text-[1.65rem] font-extrabold leading-tight text-[#0a1322]">{p.titulo}</h3>
                  <p className="mt-3 max-w-[26rem] leading-relaxed text-[#243447]">{p.texto}</p>
                  <p className="rotulo mt-4 font-semibold text-[#2f4a5e]">{p.marca}</p>
                </div>
              </Revelar>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------- capacidades */

function Capacidades() {
  return (
    <section id="capacidades" className="relative scroll-mt-8 py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-5 sm:px-8">
        <Revelar className="max-w-3xl">
          <h2 className="text-[clamp(2.1rem,4.6vw,3.8rem)] font-extrabold leading-[1] text-tx">
            Hecho para quien firma lo que audita.
          </h2>
          <p className="mt-5 max-w-2xl text-lg leading-relaxed text-tx-2">
            Una herramienta de trabajo diario: rápida de escanear, honesta cuando no sabe, y con la fuente siempre a un
            clic.
          </p>
        </Revelar>

        <div className="mt-16 grid gap-12 lg:grid-cols-12 lg:gap-14">
          {/* Citas y adendas: leídas sobre el panel de luz */}
          <Revelar className="lg:col-span-7">
            <div className="rounded-[0.6rem] border-[11px] border-[#2c3641] bg-[#2c3641]">
              <div className="panel-luz p-5 sm:p-8">
                <h3 className="max-w-md text-[1.7rem] font-extrabold leading-tight text-[#0a1322]">
                  La respuesta y su prueba, en la misma pantalla
                </h3>
                <p className="mt-3 max-w-xl text-[#243447]">
                  El modelo solo elige qué fragmentos usar; el extracto que ves es el texto real del documento, y las
                  adendas pesan más que el pliego base.
                </p>
                <div className="mt-8 grid gap-4 sm:grid-cols-2">
                  <figure className="rounded-md bg-[#0a1322] p-4 text-tx shadow-[0_16px_22px_-14px_rgb(10_19_34/0.8)]">
                    <span className="inline-flex items-center gap-1.5 rounded-md border border-eosina/45 bg-eosina/10 px-2 py-0.5 text-[0.72rem] font-semibold text-eosina">
                      <ScrollText className="size-3.5" aria-hidden />
                      Adenda N° 2 modifica este punto
                    </span>
                    <blockquote className="mt-3 font-display text-[1.05rem] font-medium leading-snug">
                      «El plazo de entrega será de quince (15) días calendario.»
                    </blockquote>
                    <figcaption className="etiqueta mt-3">Adenda 2 · pág. 1 · ejemplo</figcaption>
                  </figure>
                  <figure className="rounded-md bg-[#0a1322] p-4 text-tx shadow-[0_16px_22px_-14px_rgb(10_19_34/0.8)]">
                    <span className="inline-flex items-center gap-1.5 rounded-md border border-coral/45 bg-coral/10 px-2 py-0.5 text-[0.72rem] font-semibold text-coral">
                      <Eye className="size-3.5" aria-hidden />
                      Verificar original
                    </span>
                    <p className="mt-3 text-[0.92rem] leading-relaxed text-tx-2">
                      Sello o firma detectados en la página: conviene mirar el PDF y no fiarse solo del texto extraído.
                    </p>
                    <figcaption className="etiqueta mt-3">aviso automático</figcaption>
                  </figure>
                </div>
              </div>
            </div>
          </Revelar>

          {/* Las demás capacidades, como registro de la placa */}
          <div className="lg:col-span-5">
            <div className="divide-y divide-ink/12 border-y border-ink/12">
              <Revelar>
                <div className="py-7">
                  <h3 className="text-xl font-extrabold text-tx">Visor local desacoplado</h3>
                  <div className="mt-2 text-tx-2">
                    Vincula una carpeta de tu equipo. El original se abre en la página citada y se compara su SHA-256. No
                    se sube nada.
                  </div>
                  <div className="rotulo mt-3 text-hema">Chrome y Edge</div>
                </div>
              </Revelar>
              <Revelar retraso={0.06}>
                <div className="py-7">
                  <h3 className="text-xl font-extrabold text-tx">Prefiere callar a inventar</h3>
                  <div className="mt-2 text-tx-2">
                    Sin soporte documental, la respuesta es una abstención explícita. Nunca una conjetura con buena
                    redacción.
                  </div>
                  <div className="mt-4 rounded-md border border-dashed border-ink/30 px-3.5 py-3">
                    <p className="text-sm font-bold text-eosina">Sin evidencia suficiente</p>
                    <p className="mt-1 text-[0.85rem] leading-relaxed text-tx-2">
                      No encontré en los documentos indexados nada que responda esta pregunta.
                    </p>
                  </div>
                </div>
              </Revelar>
              <Revelar retraso={0.12}>
                <div className="py-7">
                  <h3 className="text-xl font-extrabold text-tx">El proceso, a la vista</h3>
                  <div className="mt-4">
                    <ul className="space-y-2.5">
                      {[
                        ["Antivirus y validación", true],
                        ["Texto y OCR selectivo", true],
                        ["Fragmentos y vectores", true],
                        ["PDF eliminado", false],
                      ].map(([nombre, hecho]) => (
                        <li key={String(nombre)} className="flex items-center gap-3 text-[0.95rem] font-medium text-tx">
                          <span
                            className={cn(
                              "grid size-5 place-items-center rounded-sm",
                              hecho ? "bg-hema text-[#06121a]" : "bg-eosina text-[#1a1405]",
                            )}
                            aria-hidden
                          >
                            {hecho ? <span className="font-mono text-[0.7rem] font-extrabold">✓</span> : <Trash2 className="size-3" />}
                          </span>
                          {nombre}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </Revelar>
              <Revelar retraso={0.18}>
                <div className="py-7">
                  <h3 className="text-xl font-extrabold text-tx">Cada organización, aparte</h3>
                  <div className="mt-2 text-tx-2">
                    Aislamiento por organización, permisos por expediente y un registro de auditoría que nadie puede
                    reescribir.
                  </div>
                </div>
              </Revelar>
            </div>
          </div>
        </div>
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
  ["Estado del original", "ELIMINADO"],
];

function Seguridad() {
  return (
    <section id="seguridad" className="relative scroll-mt-8 pb-24 pt-8 sm:pb-32">
      <Perforaciones />
      <div className="mx-auto mt-24 grid max-w-7xl items-center gap-14 px-5 sm:px-8 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
        <Revelar className="mx-auto w-full max-w-md">
          <div className="-rotate-[1.2deg] bg-[#f4fafc] p-7 text-[#0a1322] shadow-[0_34px_40px_-24px_rgb(0_0_0/0.9)]">
            <div className="flex items-start justify-between gap-4 border-b-2 border-[#0a1322] pb-3">
              <div>
                <p className="rotulo font-bold">MedTender · acta de purga</p>
                <p className="mt-1 font-display text-2xl font-extrabold leading-none [font-stretch:80%]">PDF ELIMINADO</p>
              </div>
              <span className="rotulo rounded-sm border border-[#0a1322] px-1.5 py-0.5 font-bold">ejemplo</span>
            </div>
            <dl className="mt-3 font-mono text-[0.78rem]">
              {FILAS_ACTA.map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between gap-4 border-b border-dashed border-[#0a1322]/30 py-2">
                  <dt className="text-[#3a5568]">{k}</dt>
                  <dd className="font-bold">{v}</dd>
                </div>
              ))}
            </dl>
            <p className="cera mt-4 -rotate-2 text-[2.1rem] leading-none text-[#0a1322]/80">verificado por el sistema</p>
          </div>
        </Revelar>

        <div>
          <Revelar>
            <h2 className="text-[clamp(2.1rem,4.6vw,3.8rem)] font-extrabold leading-[1] text-tx">
              Tus documentos son confidenciales. El diseño también.
            </h2>
          </Revelar>
          <ul className="mt-12 grid gap-x-10 gap-y-9 sm:grid-cols-2">
            {[
              [Trash2, "El PDF se elimina", "Tras indexar y verificar que todos los fragmentos tienen su vector, el archivo se borra y queda un acta con su huella."],
              [Building2, "Solo lo tuyo", "Cada consulta se filtra por organización y expediente. Lo ajeno responde «no encontrado»."],
              [ScrollText, "Auditoría de solo anexado", "Accesos, denegaciones y consultas quedan registrados sin guardar el texto de tus preguntas."],
              [Lock, "Conexión cifrada", "Todo viaja por HTTPS, con una política de seguridad estricta y sin servicios de terceros en la página."],
            ].map(([Icono, titulo, texto], i) => {
              const I = Icono as typeof Trash2;
              return (
                <li key={String(titulo)} className="border-t border-ink/15 pt-5">
                  <Revelar retraso={i * 0.08}>
                    <h3 className="flex items-center gap-2.5 text-xl font-extrabold text-tx">
                      <I className="size-5 text-hema" aria-hidden />
                      {String(titulo)}
                    </h3>
                    <p className="mt-2 leading-relaxed text-tx-2">{String(texto)}</p>
                  </Revelar>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------- voces */

const VOCES = [
  {
    texto:
      "Antes me tomaba una tarde cruzar el pliego con tres adendas. Ahora pregunto, veo la cita y abro el original para confirmar. La revisión inicial pasó de horas a minutos.",
    nombre: "Camila R.",
    cargo: "Auditora médica · hospital de ejemplo",
    grande: true,
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
    <section className="relative py-16 sm:py-24" aria-labelledby="titulo-voces">
      <div className="mx-auto max-w-7xl px-5 sm:px-8">
        <Revelar className="flex flex-wrap items-end justify-between gap-4">
          <h2 id="titulo-voces" className="max-w-2xl text-[clamp(2.1rem,4.4vw,3.4rem)] font-extrabold leading-[1.02] text-tx">
            Lo que dirían quienes lo usan.
          </h2>
          <p className="rotulo rounded-md border border-eosina/45 bg-eosina/10 px-2.5 py-1 font-semibold text-eosina">
            Testimonios de ejemplo, no son de clientes reales
          </p>
        </Revelar>
        <div className="mt-12 grid gap-x-12 gap-y-10 lg:grid-cols-5">
          {VOCES.map((v, i) => (
            <Revelar key={v.nombre} retraso={i * 0.1} className={v.grande ? "lg:col-span-3" : "lg:col-span-2"}>
              <figure className="flex h-full flex-col justify-between border-t-2 border-ink/25 pt-6">
                <blockquote
                  className={cn(
                    "font-display font-medium leading-snug text-tx",
                    v.grande ? "text-[1.6rem] sm:text-[1.95rem]" : "text-[1.2rem]",
                  )}
                >
                  «{v.texto}»
                </blockquote>
                <figcaption className="mt-7 flex items-center gap-3">
                  <span className="grid size-10 place-items-center rounded-md bg-luz font-display text-base font-extrabold text-[#07101c]" aria-hidden>
                    {v.nombre[0]}
                  </span>
                  <span className="leading-tight">
                    <span className="block font-bold text-tx">{v.nombre}</span>
                    <span className="block text-sm text-tx-2">{v.cargo}</span>
                  </span>
                </figcaption>
              </figure>
            </Revelar>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ cierre */

function Cierre() {
  return (
    <section className="relative isolate mt-10 overflow-hidden pb-10 pt-20 sm:pt-28">
      <div
        className="absolute inset-0 -z-10 bg-[radial-gradient(50%_80%_at_50%_0%,rgb(124_212_230/0.13),transparent_70%)]"
        aria-hidden
      />
      <Perforaciones className="absolute inset-x-0 top-0" />
      <div className="mx-auto max-w-4xl px-5 text-center sm:px-8">
        <Revelar>
          <h2 className="text-[clamp(2.3rem,5.2vw,4.4rem)] font-extrabold leading-[1] text-tx">
            El próximo pliego, con la fuente a un clic.
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-lg text-tx-2">Ingresa con tu organización y crea tu primer expediente.</p>
          <div className="mt-9 flex justify-center">
            <Link to="/ingreso" className={boton({ variante: "primario", tamano: "lg" })}>
              Ingresar a MedTender
              <ArrowRight className="size-[1.1rem]" aria-hidden />
            </Link>
          </div>
        </Revelar>
      </div>
      <footer className="mx-auto mt-24 flex max-w-7xl flex-col items-center justify-between gap-3 border-t border-ink/15 px-5 py-7 text-sm text-tx-2 sm:flex-row sm:px-8">
        <Marca />
        <p>Los textos de las tarjetas de esta página son ejemplos ilustrativos.</p>
      </footer>
    </section>
  );
}
