import { ArrowRight, ScrollText, SearchX } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ActaPurga, EscenaExpediente, VisorDocumento } from "../arte/Folios";
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
      initial={quieto ? false : { opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.6, delay: retraso, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}

export function PaginaBienvenida() {
  return (
    <div className="relative overflow-x-clip bg-mesa">
      <Navegacion />
      <Heroe />
      <Prueba />
      <ComoFunciona />
      <Honestidad />
      <Seguridad />
      <Cierre />
    </div>
  );
}

/* -------------------------------------------------------------- navegación */

function Navegacion() {
  const [fondo, setFondo] = useState(false);
  useEffect(() => {
    const alBajar = () => setFondo(window.scrollY > 24);
    alBajar();
    window.addEventListener("scroll", alBajar, { passive: true });
    return () => window.removeEventListener("scroll", alBajar);
  }, []);
  const enlace = "rounded-md px-4 py-2 text-[0.95rem] text-tinta transition-colors hover:bg-tinta/10";
  return (
    <header className={cn("fixed inset-x-0 top-0 z-40 transition-colors duration-300", fondo ? "border-b border-tinta/15 bg-mesa" : "border-b border-transparent")}>
      <div className="mx-auto flex max-w-[1200px] items-center justify-between px-5 py-3 sm:px-8">
        <Link to="/" aria-label="MedTender, inicio">
          <Marca />
        </Link>
        <nav className="hidden items-center md:flex" aria-label="Secciones">
          <a href="#como-funciona" className={enlace}>Cómo funciona</a>
          <a href="#honestidad" className={enlace}>Qué responde</a>
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
    <section className="mx-auto grid min-h-[100svh] max-w-[1200px] items-center gap-12 px-5 pb-20 pt-28 sm:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:gap-14">
      <div>
        <Revelar>
          <h1 className="text-[clamp(2.4rem,5vw,4rem)]">
            Pregunta a tu expediente.
            <span className="block">El PDF no se queda.</span>
          </h1>
        </Revelar>
        <Revelar retraso={0.08}>
          <p className="mt-6 max-w-[32rem] text-[1.1rem] leading-[1.55] text-tinta-2">
            Cada respuesta llega con el extracto literal, la página y la huella del archivo. Tus originales se indexan, se eliminan del
            servidor y se abren solo desde tu equipo.
          </p>
        </Revelar>
        <Revelar retraso={0.16} className="mt-9 flex flex-wrap items-center gap-3">
          <Link to="/ingreso" className={boton({ variante: "primario", tamano: "lg" })}>
            Ingresar
            <ArrowRight className="size-[1.1rem]" aria-hidden />
          </Link>
          <a href="#como-funciona" className={boton({ variante: "secundario", tamano: "lg" })}>
            Ver cómo funciona
          </a>
        </Revelar>
        <Revelar retraso={0.24}>
          <p className="mt-8 max-w-[30rem] text-[0.88rem] leading-relaxed text-tinta-3">
            Para auditores médicos, ingenieros biomédicos y abogados de entidades de salud que revisan pliegos, adendas y fichas técnicas.
          </p>
        </Revelar>
      </div>
      <EscenaExpediente />
    </section>
  );
}

function Titular({ children, className }: { children: ReactNode; className?: string }) {
  return <h2 className={cn("text-[clamp(1.8rem,3.2vw,2.5rem)]", className)}>{children}</h2>;
}

/* ------------------------------------------------------------------ prueba */

function Prueba() {
  return (
    <section className="mx-auto max-w-[1200px] border-t border-tinta/15 px-5 py-20 sm:px-8 sm:py-28">
      <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:gap-16">
        <Revelar>
          <Titular>Cada respuesta llega con su prueba.</Titular>
          <ul className="mt-7 max-w-[30rem] space-y-4 text-[1.02rem] leading-relaxed text-tinta-2">
            <li>
              <b className="font-semibold text-tinta">Documento, página y extracto literal.</b> El modelo solo elige qué fragmentos usar; el
              texto que ves es el del documento.
            </li>
            <li>
              <b className="font-semibold text-tinta">La huella se compara en tu navegador.</b> Abres el original desde tu carpeta y
              comparamos su SHA-256 con el que registramos al indexarlo.
            </li>
            <li>
              <b className="font-semibold text-tinta">El archivo no sale de tu equipo.</b> Funciona en Chrome y Edge.
            </li>
          </ul>
        </Revelar>
        <Revelar retraso={0.1}>
          <VisorDocumento />
        </Revelar>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------ cómo funciona */

const PASOS: [string, string][] = [
  ["Subes el pliego", "Arrastras los PDF del expediente. Revisamos que sean válidos, sin virus y sin contraseña de apertura antes de seguir."],
  [
    "Lo indexamos y lo borramos",
    "Extraemos el texto (con OCR solo donde hace falta), lo partimos en fragmentos y lo convertimos en vectores. Con el índice verificado, el PDF se elimina y queda un acta de purga.",
  ],
  ["Preguntas y compruebas", "Obtienes la respuesta con la cita exacta y la huella del archivo. Si no hay evidencia, te lo dice en lugar de conjeturar."],
];

function ComoFunciona() {
  return (
    <section id="como-funciona" className="mx-auto max-w-[1200px] scroll-mt-16 border-t border-tinta/15 px-5 py-20 sm:px-8 sm:py-28">
      <Revelar className="max-w-2xl">
        <Titular>Tres pasos, y tu archivo nunca se queda.</Titular>
      </Revelar>
      <ol className="mt-12 grid gap-x-10 gap-y-10 lg:grid-cols-3">
        {PASOS.map(([titulo, texto], i) => (
          <li key={titulo}>
            <Revelar retraso={i * 0.07}>
              <p className="font-display text-[2.6rem] font-semibold leading-none text-tinta-3" aria-hidden>
                {i + 1}
              </p>
              <h3 className="mt-3 text-[1.35rem]">{titulo}</h3>
              <p className="mt-2 leading-relaxed text-tinta-2">{texto}</p>
            </Revelar>
          </li>
        ))}
      </ol>
    </section>
  );
}

/* --------------------------------------------------------------- honestidad */

function Honestidad() {
  return (
    <section id="honestidad" className="mx-auto max-w-[1200px] scroll-mt-16 border-t border-tinta/15 px-5 py-20 sm:px-8 sm:py-28">
      <Revelar className="max-w-2xl">
        <Titular>Las adendas pesan más. Y cuando no sabe, lo dice.</Titular>
        <p className="mt-5 text-[1.05rem] leading-relaxed text-tinta-2">
          Una herramienta de trabajo diario: honesta cuando no hay soporte y con la fuente siempre a un clic. Ejemplos ilustrativos.
        </p>
      </Revelar>
      <div className="mt-12 grid gap-6 lg:grid-cols-2">
        <Revelar>
          <article className="folio h-full p-6 sm:p-8">
            <Insignia tono="aviso">
              <ScrollText className="size-3.5" aria-hidden />
              Adenda N° 2 modifica este punto
            </Insignia>
            <h3 className="mt-4 text-[1.3rem]">Cuando una adenda cambia el pliego, la respuesta lo señala</h3>
            <p className="mt-3 font-display text-[1.02rem] leading-[1.7]">
              <span className="resaltado">«El plazo de entrega será de quince (15) días calendario.»</span>
            </p>
            <p className="etiqueta mt-2">Adenda 2 · pág. 1 · ejemplo</p>
            <p className="mt-4 text-[0.92rem] leading-relaxed text-tinta-2">
              Entre adendas prevalece la de mayor número, y la respuesta advierte si hay otra adenda relacionada que no se citó.
            </p>
          </article>
        </Revelar>
        <Revelar retraso={0.08}>
          <article className="folio h-full p-6 sm:p-8">
            <Insignia tono="aviso">
              <SearchX className="size-3.5" aria-hidden />
              Sin evidencia suficiente
            </Insignia>
            <h3 className="mt-4 text-[1.3rem]">Prefiere callar a inventar</h3>
            <p className="mt-3 text-[0.98rem] leading-relaxed">
              No encontré en los documentos indexados nada que responda esta pregunta. Reformúlela o verifique que el documento pertinente esté
              cargado.
            </p>
            <p className="mt-4 text-[0.92rem] leading-relaxed text-tinta-2">
              Sin soporte documental, la respuesta es una abstención explícita; nunca una conjetura con buena redacción. Si el fragmento tiene
              un sello, una tabla o un OCR dudoso, te avisa que conviene mirar el original.
            </p>
          </article>
        </Revelar>
      </div>
    </section>
  );
}

/* --------------------------------------------------------------- seguridad */

const GARANTIAS: [string, string][] = [
  ["El PDF se elimina.", "Tras indexar y verificar que todos los fragmentos tienen su vector, el archivo se borra y queda un acta con su huella."],
  ["Solo lo tuyo.", "Cada consulta se filtra por organización y por expediente, también dentro de la base de datos. Lo ajeno responde «no encontrado»."],
  ["Auditoría de solo anexado.", "Accesos, denegaciones y consultas quedan registrados sin guardar el texto de tus preguntas."],
  ["Conexión cifrada.", "Todo viaja por HTTPS, con una política de seguridad estricta y sin servicios de terceros en la página."],
];

function Seguridad() {
  return (
    <section id="seguridad" className="mx-auto max-w-[1200px] scroll-mt-16 border-t border-tinta/15 px-5 py-20 sm:px-8 sm:py-28">
      <div className="grid items-start gap-12 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] lg:gap-16">
        <div>
          <Revelar>
            <Titular>Tus documentos son confidenciales. El diseño también.</Titular>
          </Revelar>
          <ul className="mt-8 space-y-5">
            {GARANTIAS.map(([titulo, texto], i) => (
              <li key={titulo}>
                <Revelar retraso={i * 0.05}>
                  <p className="leading-relaxed text-tinta-2">
                    <b className="font-semibold text-tinta">{titulo}</b> {texto}
                  </p>
                </Revelar>
              </li>
            ))}
          </ul>
        </div>
        <Revelar retraso={0.1}>
          <ActaPurga />
        </Revelar>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ cierre */

function Cierre() {
  return (
    <section className="border-t border-tinta/15 bg-carpeta px-5 py-24 sm:py-28">
      <Revelar className="mx-auto max-w-3xl text-center">
        <h2 className="text-[clamp(2rem,4.4vw,3.2rem)]">El próximo pliego, con la fuente a un clic.</h2>
        <p className="mx-auto mt-4 max-w-xl text-[1.05rem] text-tinta">Ingresa con tu organización y abre tu primer expediente.</p>
        <div className="mt-9 flex justify-center">
          <Link to="/ingreso" className={boton({ variante: "primario", tamano: "lg" })}>
            Ingresar a MedTender
            <ArrowRight className="size-[1.1rem]" aria-hidden />
          </Link>
        </div>
      </Revelar>
      <footer className="mx-auto mt-24 flex max-w-[1200px] flex-col items-center justify-between gap-3 text-[0.78rem] text-tinta sm:flex-row">
        <Marca />
        <p>Los documentos y respuestas de esta página son ejemplos ilustrativos.</p>
      </footer>
    </section>
  );
}
