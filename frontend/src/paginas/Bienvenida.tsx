import {
  ArrowRight,
  BadgeCheck,
  ClipboardCheck,
  Eye,
  FileText,
  HardDriveDownload,
  Quote,
  ScrollText,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { CampoMicroscopio } from "../arte/CampoMicroscopio";
import { BarraEscala, Celula, Escudo, Fibra, Molecula } from "../arte/Decoracion";
import { Tejido } from "../arte/Tejido";
import { Marca } from "../componentes/Marca";
import { boton } from "../componentes/ui/Boton";
import { Insignia } from "../componentes/ui/Insignia";
import { cn } from "../lib/cn";

/** Aparece al entrar en pantalla (una sola vez), con la misma curva que el resto de la interfaz. */
function Revelar({ children, retraso = 0, className }: { children: ReactNode; retraso?: number; className?: string }) {
  const quieto = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={quieto ? false : { opacity: 0, y: 28 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.8, delay: retraso, ease: [0.16, 1, 0.3, 1] }}
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
  const enlace = "rounded-lg px-3.5 py-2 transition-colors hover:bg-hema/8 hover:text-hema-osc";
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
      {/* El tejido ocupa toda la sección; un lavado claro lo retira detrás del titular. */}
      <div className="absolute inset-0 -z-10" aria-hidden>
        <Tejido semilla={5} celula={72} tinte={0.55} lavanda={0.45} />
        <div className="absolute inset-0 bg-[linear-gradient(95deg,var(--color-lila-50)_28%,rgb(251_247_253/0.82)_52%,rgb(251_247_253/0.25)_100%)]" />
        <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-lila-50 to-transparent" />
      </div>

      <div className="mx-auto grid max-w-7xl items-center gap-8 px-5 pb-20 pt-28 sm:px-8 lg:min-h-[100svh] lg:grid-cols-[minmax(0,1fr)_minmax(0,1.02fr)] lg:gap-6 lg:pb-14">
        <div className="relative z-10">
          <Revelar>
            <h1 className="text-[clamp(2.7rem,6.3vw,5.5rem)] font-bold leading-[0.97] tracking-[-0.04em] text-ink">
              Pregunta a tu expediente.
              <span className="mt-2 block text-eosina">El PDF no se queda.</span>
            </h1>
          </Revelar>
          <Revelar retraso={0.12}>
            <p className="mt-7 max-w-[33rem] text-[1.14rem] leading-relaxed text-tx-2">
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

        <Revelar retraso={0.1} className="relative lg:-mr-10">
          <CampoMicroscopio />
        </Revelar>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------- cómo funciona */

/** Un campo de microscopio pequeño: la ilustración de cada paso. */
function Campo({ children, tono = "eosina" }: { children: ReactNode; tono?: "eosina" | "hema" }) {
  return (
    <div className="relative mx-auto size-44 sm:size-52">
      <div className="graticula absolute -inset-1 rounded-full opacity-60" aria-hidden />
      <div
        className={cn(
          "absolute inset-1 grid place-items-center overflow-hidden rounded-full border-[7px] border-hema-pro shadow-[0_24px_40px_-22px_rgb(28_23_82/0.7)]",
          tono === "eosina" ? "bg-eosina-clara" : "bg-[#d4cdf6]",
        )}
      >
        <Tejido semilla={tono === "eosina" ? 21 : 33} celula={34} tinte={0.75} lavanda={tono === "eosina" ? 0.2 : 0.8} />
        <div className="relative">{children}</div>
      </div>
    </div>
  );
}

const PASOS: { titulo: string; texto: string; marca: string }[] = [
  {
    titulo: "Sube el pliego",
    texto: "Arrastra los PDF del expediente. Revisamos que sean válidos, sin virus y sin contraseña de apertura antes de seguir.",
    marca: "validación y antivirus",
  },
  {
    titulo: "Lo indexamos y lo borramos",
    texto:
      "Extraemos el texto (con OCR solo donde hace falta), lo partimos en fragmentos y lo convertimos en vectores. Con el índice verificado, el PDF se elimina y queda un acta de purga.",
    marca: "el original no queda en el servidor",
  },
  {
    titulo: "Pregunta y comprueba",
    texto:
      "Cada respuesta cita documento, página y extracto literal. Para verificarla, abre el original desde tu carpeta: comparamos su huella SHA-256 sin que el archivo salga de tu equipo.",
    marca: "cita verificable",
  },
];

function ComoFunciona() {
  return (
    <section id="como-funciona" className="relative scroll-mt-8 py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-5 sm:px-8">
        <Revelar className="max-w-3xl">
          <h2 className="text-[clamp(2rem,4.4vw,3.6rem)] font-bold leading-[1.02] text-ink">
            Tres pasos, y tu archivo nunca se queda.
          </h2>
        </Revelar>

        <ol className="relative mt-16 grid gap-14 lg:grid-cols-3 lg:gap-8">
          {PASOS.map((p, i) => (
            <Revelar key={p.titulo} retraso={i * 0.12}>
              <li className="text-center">
                <Campo tono={i === 1 ? "hema" : "eosina"}>
                  {i === 0 && (
                    <div className="grid size-16 -rotate-6 place-items-center rounded-lg bg-white shadow-[0_14px_22px_-10px_rgb(28_23_82/0.6)]">
                      <HardDriveDownload className="size-8 text-hema" strokeWidth={1.6} aria-hidden />
                    </div>
                  )}
                  {i === 1 && (
                    <div className="relative size-24">
                      <Celula className="absolute left-0 top-2 w-12" rotacion={-10} />
                      <Celula className="absolute right-0 top-0 w-12" tono="lavanda" rotacion={20} />
                      <Celula className="absolute bottom-0 left-6 w-12" rotacion={30} />
                    </div>
                  )}
                  {i === 2 && (
                    <div className="relative size-24">
                      <Celula className="absolute left-3 top-3 w-[4.6rem]" rotacion={8} />
                      <span className="absolute -right-4 -top-1 rounded-md bg-ink px-1.5 py-0.5 font-mono text-[0.68rem] font-bold text-white">
                        [1]
                      </span>
                      <span className="absolute left-12 top-2 h-px w-8 rotate-[-35deg] bg-ink" aria-hidden />
                    </div>
                  )}
                </Campo>
                <div className="mt-8">
                  <h3 className="text-2xl font-bold text-ink">
                    <span className="mr-2 font-mono text-lg font-bold text-eosina">{i + 1}</span>
                    {p.titulo}
                  </h3>
                  <p className="mx-auto mt-3 max-w-[26rem] leading-relaxed text-tx-2">{p.texto}</p>
                  <p className="etiqueta mt-4 inline-flex items-center gap-2 font-semibold !text-hema-osc">
                    <span className="size-1.5 rounded-full bg-eosina" aria-hidden />
                    {p.marca}
                  </p>
                </div>
              </li>
            </Revelar>
          ))}
        </ol>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------- capacidades */

function Capacidades() {
  return (
    <section id="capacidades" className="relative scroll-mt-8 py-16 sm:py-24">
      <div className="mx-auto max-w-7xl px-5 sm:px-8">
        <Revelar className="max-w-3xl">
          <h2 className="text-[clamp(2rem,4.4vw,3.6rem)] font-bold leading-[1.02] text-ink">
            Hecho para quien firma lo que audita.
          </h2>
          <p className="mt-5 max-w-2xl text-lg leading-relaxed text-tx-2">
            Una herramienta de trabajo diario: rápida de escanear, honesta cuando no sabe, y con la fuente siempre a un
            clic.
          </p>
        </Revelar>

        <div className="mt-14 grid gap-5 lg:grid-cols-6">
          {/* Hematoxilina: citas */}
          <Revelar className="lg:col-span-4">
            <article className="relative h-full overflow-hidden rounded-[2rem] bg-hema-pro p-7 text-white sm:p-10">
              <div className="absolute inset-0 opacity-25" aria-hidden>
                <Tejido semilla={41} celula={60} tinte={0.9} lavanda={0.9} />
              </div>
              <Quote className="absolute -right-3 -top-3 size-36 text-white/[0.08]" aria-hidden />
              <h3 className="relative text-2xl font-bold sm:text-3xl">La respuesta y su prueba, en la misma pantalla</h3>
              <p className="relative mt-3 max-w-xl text-white/80">
                El modelo solo elige qué fragmentos usar; el extracto que ves es el texto real del documento, y las
                adendas pesan más que el pliego base.
              </p>
              <div className="relative mt-8 grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl bg-white p-4 text-ink">
                  <Insignia tono="ambar">
                    <ScrollText className="size-3.5" aria-hidden />
                    Adenda N° 2 modifica este punto
                  </Insignia>
                  <p className="mt-3 font-display text-[1.05rem] font-medium leading-snug">
                    «El plazo de entrega será de quince (15) días calendario.»
                  </p>
                  <p className="etiqueta mt-3">Adenda 2 · pág. 1 · ejemplo</p>
                </div>
                <div className="rounded-2xl bg-white p-4 text-ink">
                  <Insignia tono="coral">
                    <Eye className="size-3.5" aria-hidden />
                    Verificar original
                  </Insignia>
                  <p className="mt-3 text-[0.92rem] leading-relaxed text-tx-2">
                    Sello o firma detectados en la página: conviene mirar el PDF y no fiarse solo del texto extraído.
                  </p>
                  <p className="etiqueta mt-3">aviso automático</p>
                </div>
              </div>
            </article>
          </Revelar>

          {/* Visor local */}
          <Revelar retraso={0.1} className="lg:col-span-2">
            <article className="vidrio relative h-full overflow-hidden rounded-[2rem] p-7">
              <Molecula className="absolute -right-6 -top-4 w-48" />
              <h3 className="mt-24 text-2xl font-bold text-ink">Visor local desacoplado</h3>
              <p className="mt-3 text-tx-2">
                Vincula una carpeta de tu equipo. El original se abre en la página citada y se compara su SHA-256. No se
                sube nada.
              </p>
              <p className="etiqueta mt-5 font-semibold !text-hema-osc">Chrome y Edge</p>
            </article>
          </Revelar>

          {/* Eosina: abstención */}
          <Revelar retraso={0.05} className="lg:col-span-2">
            <article className="relative h-full overflow-hidden rounded-[2rem] bg-eosina p-7 text-white">
              <div className="absolute inset-0 opacity-30 mix-blend-soft-light" aria-hidden>
                <Tejido semilla={57} celula={44} tinte={1} lavanda={0.1} />
              </div>
              <div className="relative rounded-2xl bg-white p-4 text-ink shadow-[0_16px_28px_-16px_rgb(28_23_82/0.6)]">
                <p className="text-sm font-bold text-ambar">Sin evidencia suficiente</p>
                <p className="mt-1 text-[0.85rem] leading-relaxed text-tx-2">
                  No encontré en los documentos indexados nada que responda esta pregunta.
                </p>
              </div>
              <h3 className="relative mt-6 text-2xl font-bold">Prefiere callar a inventar</h3>
              <p className="relative mt-3 text-white/90">
                Sin soporte documental, la respuesta es una abstención explícita. Nunca una conjetura con buena
                redacción.
              </p>
            </article>
          </Revelar>

          {/* Pipeline */}
          <Revelar retraso={0.1} className="lg:col-span-2">
            <article className="vidrio h-full rounded-[2rem] p-7">
              <h3 className="text-2xl font-bold text-ink">El proceso, a la vista</h3>
              <ul className="mt-6 space-y-3.5">
                {[
                  ["Antivirus y validación", true],
                  ["Texto y OCR selectivo", true],
                  ["Fragmentos y vectores", true],
                  ["PDF eliminado", false],
                ].map(([nombre, hecho]) => (
                  <li key={String(nombre)} className="flex items-center gap-3 text-[0.95rem] font-medium">
                    <span
                      className={cn(
                        "grid size-6 place-items-center rounded-full",
                        hecho ? "bg-hema text-white" : "bg-eosina/15 text-eosina-osc ring-1 ring-eosina/60",
                      )}
                    >
                      {hecho ? <BadgeCheck className="size-4" aria-hidden /> : <Trash2 className="size-3.5" aria-hidden />}
                    </span>
                    {nombre}
                  </li>
                ))}
              </ul>
            </article>
          </Revelar>

          {/* Organizaciones y auditoría */}
          <Revelar retraso={0.15} className="lg:col-span-2">
            <article className="vidrio relative h-full overflow-hidden rounded-[2rem] p-7">
              <ClipboardCheck className="size-8 text-hema" strokeWidth={1.5} aria-hidden />
              <h3 className="mt-4 text-2xl font-bold text-ink">Cada organización, aparte</h3>
              <p className="mt-3 max-w-[17rem] text-tx-2">
                Aislamiento por organización, permisos por expediente y un registro de auditoría que nadie puede
                reescribir.
              </p>
              <Celula className="absolute -bottom-5 -right-5 w-28 opacity-90" tono="lavanda" rotacion={-14} />
              <Celula className="absolute -bottom-1 right-14 w-16 opacity-90" rotacion={20} />
            </article>
          </Revelar>
        </div>
      </div>
    </section>
  );
}

/* --------------------------------------------------------------- seguridad */

function Seguridad() {
  return (
    <section id="seguridad" className="relative scroll-mt-8 py-24 sm:py-32">
      <div className="mx-auto grid max-w-7xl items-center gap-12 px-5 sm:px-8 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <Revelar className="mx-auto w-full max-w-[18rem] lg:max-w-sm">
          <div className="relative">
            <div className="absolute inset-[-12%] -z-10 overflow-hidden rounded-full opacity-80" aria-hidden>
              <Tejido semilla={77} celula={40} tinte={0.6} lavanda={0.5} />
            </div>
            <Escudo className="w-full motion-safe:animate-flotar drop-shadow-[0_24px_24px_rgb(28_23_82/0.3)]" />
          </div>
        </Revelar>
        <div>
          <Revelar>
            <h2 className="text-[clamp(2rem,4.4vw,3.6rem)] font-bold leading-[1.02] text-ink">
              Tus documentos son confidenciales. El diseño también.
            </h2>
          </Revelar>
          <ul className="mt-10 grid gap-x-10 gap-y-8 sm:grid-cols-2">
            {[
              ["El PDF se elimina", "Tras indexar y verificar que todos los fragmentos tienen su vector, el archivo se borra y queda un acta con su huella."],
              ["Solo lo tuyo", "Cada consulta se filtra por organización y expediente. Lo ajeno responde «no encontrado»."],
              ["Auditoría de solo anexado", "Accesos, denegaciones y consultas quedan registrados sin guardar el texto de tus preguntas."],
              ["Conexión cifrada", "Todo viaja por HTTPS, con una política de seguridad estricta y sin servicios de terceros en la página."],
            ].map(([titulo, texto], i) => (
              <Revelar key={titulo} retraso={i * 0.08}>
                <li>
                  <h3 className="flex items-center gap-2.5 text-xl font-bold text-ink">
                    <ShieldCheck className="size-5 text-eosina" aria-hidden />
                    {titulo}
                  </h3>
                  <p className="mt-2 leading-relaxed text-tx-2">{texto}</p>
                </li>
              </Revelar>
            ))}
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
          <h2 id="titulo-voces" className="max-w-2xl text-[clamp(2rem,4.2vw,3.2rem)] font-bold leading-[1.04] text-ink">
            Lo que dirían quienes lo usan.
          </h2>
          <Insignia tono="ambar">Testimonios de ejemplo, no son de clientes reales</Insignia>
        </Revelar>
        <div className="mt-12 grid gap-5 lg:grid-cols-5">
          {VOCES.map((v, i) => (
            <Revelar key={v.nombre} retraso={i * 0.1} className={v.grande ? "lg:col-span-3" : "lg:col-span-2"}>
              <figure className="vidrio relative flex h-full flex-col justify-between overflow-hidden rounded-[2rem] p-7 sm:p-9">
                <Quote className="absolute right-5 top-5 size-14 text-eosina/[0.14]" aria-hidden />
                <blockquote className={cn("relative font-display font-medium leading-snug text-ink", v.grande ? "text-[1.55rem] sm:text-[1.85rem]" : "text-[1.15rem]")}>
                  «{v.texto}»
                </blockquote>
                <figcaption className="relative mt-7 flex items-center gap-3">
                  <span className="grid size-10 place-items-center rounded-xl bg-gradient-to-br from-eosina to-hema font-display text-sm font-bold text-white" aria-hidden>
                    {v.nombre[0]}
                  </span>
                  <span className="leading-tight">
                    <span className="block font-bold text-ink">{v.nombre}</span>
                    <span className="block text-sm text-tx-3">{v.cargo}</span>
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
    <section className="relative isolate mt-10 overflow-hidden bg-hema-pro pb-10 pt-20 text-white sm:pt-28">
      <div className="absolute inset-0 -z-10 opacity-30" aria-hidden>
        <Tejido semilla={91} celula={70} tinte={0.9} lavanda={0.85} />
      </div>
      <Fibra className="absolute inset-x-0 top-0 -z-0 opacity-70" />
      <div className="mx-auto max-w-4xl px-5 text-center sm:px-8">
        <Revelar>
          <h2 className="text-[clamp(2.2rem,5vw,4.2rem)] font-bold leading-[1.02]">
            El próximo pliego, con la fuente a un clic.
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-lg text-white/80">
            Ingresa con tu organización y crea tu primer expediente.
          </p>
          <div className="mt-9 flex justify-center">
            <Link to="/ingreso" className={boton({ variante: "primario", tamano: "lg" })}>
              Ingresar a MedTender
              <ArrowRight className="size-[1.1rem]" aria-hidden />
            </Link>
          </div>
        </Revelar>
      </div>
      <footer className="mx-auto mt-24 flex max-w-7xl flex-col items-center justify-between gap-3 border-t border-white/15 px-5 py-7 text-sm text-white/70 sm:flex-row sm:px-8">
        <Marca oscuro />
        <p className="flex items-center gap-3">
          <BarraEscala micras={50} className="!text-white" />
          Los textos de las tarjetas de esta página son ejemplos ilustrativos.
        </p>
      </footer>
    </section>
  );
}
