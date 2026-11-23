import { ArrowRight, ScrollText, SearchX } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { EscenaExpediente, VisorDocumento } from "../arte/Folios";
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
      <Casos />
      <Prueba />
      <ComoFunciona />
      <Honestidad />
      <Cuidado />
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
          <a href="#casos" className={enlace}>Qué resuelve</a>
          <a href="#como-funciona" className={enlace}>Cómo funciona</a>
          <a href="#cuidado" className={enlace}>Seguridad</a>
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
          <h1 className="text-[clamp(2.2rem,4.3vw,3.5rem)]">
            Pregunta a tus expedientes de salud.
            <span className="block">Con la fuente a la vista.</span>
          </h1>
        </Revelar>
        <Revelar retraso={0.08}>
          <p className="mt-6 max-w-[33rem] text-[1.1rem] leading-[1.55] text-tinta-2">
            El asistente para clínicas, hospitales y aseguradoras: consulta licitaciones médicas, historias clínicas y auditorías, y cada
            respuesta llega con el documento, la página y el texto exacto.
          </p>
        </Revelar>
        <Revelar retraso={0.16} className="mt-9 flex flex-wrap items-center gap-3">
          <Link to="/ingreso" className={boton({ variante: "primario", tamano: "lg" })}>
            Ingresar
            <ArrowRight className="size-[1.1rem]" aria-hidden />
          </Link>
          <a href="#casos" className={boton({ variante: "secundario", tamano: "lg" })}>
            Ver qué resuelve
          </a>
        </Revelar>
        <Revelar retraso={0.24}>
          <p className="mt-8 max-w-[32rem] text-[0.88rem] leading-relaxed text-tinta-3">
            Para auditores médicos, ingenieros biomédicos y abogados de entidades de salud.{" "}
            <Link to="/registro" className="font-semibold text-accion underline underline-offset-4">
              ¿Eres paciente o familiar? Crea tu cuenta personal.
            </Link>
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

/* ------------------------------------------------------------------- casos */

const CASOS: { titulo: string; texto: string; pregunta: string }[] = [
  {
    titulo: "Licitaciones médicas",
    texto:
      "Pliegos, adendas, fichas técnicas y registros sanitarios en un solo expediente. Pregunta por plazos, garantías o requisitos habilitantes y mira qué adenda modifica el pliego.",
    pregunta: "¿Qué garantías y pólizas exige esta licitación?",
  },
  {
    titulo: "Historias clínicas y auditoría",
    texto:
      "Revisa historias clínicas, glosas y soportes con la cita exacta de cada folio, para auditar sin leer cientos de páginas a mano.",
    pregunta: "¿Qué soporte hay en la historia clínica para esta glosa?",
  },
  {
    titulo: "Medicamentos de Colombia",
    texto:
      "Registro sanitario, titular, vigencia, presentaciones y precio máximo regulado, con los datos abiertos de INVIMA, y efectos, contraindicaciones e interacciones con fichas técnicas oficiales citadas. No indica dosis ni dice qué tomar.",
    pregunta: "¿Está vigente el registro de la losartán de Genfar?",
  },
];

function Casos() {
  return (
    <section id="casos" className="mx-auto max-w-[1200px] scroll-mt-16 border-t border-tinta/15 px-5 py-20 sm:px-8 sm:py-28">
      <Revelar className="max-w-2xl">
        <Titular>Hecho para el trabajo diario de la salud.</Titular>
      </Revelar>
      <ul className="mt-12 grid gap-x-10 gap-y-12 lg:grid-cols-3">
        {CASOS.map((c, i) => (
          <li key={c.titulo}>
            <Revelar retraso={i * 0.07}>
              <h3 className="text-[1.4rem]">{c.titulo}</h3>
              <p className="mt-3 leading-relaxed text-tinta-2">{c.texto}</p>
              <p className="mt-5 border-t border-tinta/12 pt-3 font-display text-[1rem] leading-snug text-tinta">«{c.pregunta}»</p>
              <p className="etiqueta mt-1.5">Pregunta de ejemplo</p>
            </Revelar>
          </li>
        ))}
      </ul>
    </section>
  );
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
              <b className="font-semibold text-tinta">Documento, página y texto exacto.</b> El modelo solo elige qué fragmentos usar; lo que ves
              es lo que dice el documento.
            </li>
            <li>
              <b className="font-semibold text-tinta">Abres el original y lo compruebas.</b> Desde tu carpeta, comparamos su huella SHA-256 con
              la registrada. Funciona en Chrome y Edge.
            </li>
            <li>
              <b className="font-semibold text-tinta">Te avisa cuando conviene mirar el original.</b> Sellos, tablas y escaneos dudosos quedan
              señalados en la propia cita.
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
  ["Reúnes el expediente", "Subes la licitación, las historias clínicas o las fichas técnicas. Revisamos que los archivos sean válidos y estén libres de virus."],
  [
    "Preguntas en tus palabras",
    "Leemos los documentos (con OCR en las páginas escaneadas) y buscamos por significado y por términos exactos, como un código CUM, un registro INVIMA o un número de adenda.",
  ],
  ["Compruebas la fuente", "Obtienes la respuesta con la cita exacta. Si los documentos no la respaldan, te lo dice en lugar de conjeturar."],
];

function ComoFunciona() {
  return (
    <section id="como-funciona" className="mx-auto max-w-[1200px] scroll-mt-16 border-t border-tinta/15 px-5 py-20 sm:px-8 sm:py-28">
      <Revelar className="max-w-2xl">
        <Titular>De la pila de documentos a la respuesta, en tres pasos.</Titular>
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
          En salud, una respuesta inventada es peor que ninguna. Ejemplos ilustrativos.
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

/* ------------------------------------------------------------------ cuidado */

const GARANTIAS: [string, string][] = [
  ["Tus originales no se quedan en el servidor.", "Se procesan, se verifica el índice y se eliminan; tú conservas los archivos en tu equipo."],
  ["Solo lo de tu organización.", "Cada consulta se filtra por organización y por expediente, también dentro de la base de datos. Lo ajeno responde «no encontrado»."],
  ["Auditoría de solo anexado.", "Accesos, denegaciones y consultas quedan registrados sin guardar el texto de tus preguntas."],
  ["Conexión cifrada.", "Todo viaja por HTTPS, con una política de seguridad estricta y sin servicios de terceros en la página."],
];

function Cuidado() {
  return (
    <section id="cuidado" className="mx-auto max-w-[1200px] scroll-mt-16 border-t border-tinta/15 px-5 py-20 sm:px-8 sm:py-28">
      <Revelar className="max-w-2xl">
        <Titular>Información de salud, tratada con cuidado.</Titular>
      </Revelar>
      <ul className="mt-10 grid gap-x-12 gap-y-7 md:grid-cols-2">
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
    </section>
  );
}

/* ------------------------------------------------------------------ cierre */

function Cierre() {
  return (
    <section className="border-t border-tinta/15 bg-carpeta px-5 py-24 sm:py-28">
      <Revelar className="mx-auto max-w-3xl text-center">
        <h2 className="text-[clamp(2rem,4.4vw,3.2rem)]">Tu próxima licitación o auditoría, con la fuente a un clic.</h2>
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
        <p>Los documentos, preguntas y respuestas de esta página son ejemplos ilustrativos.</p>
      </footer>
    </section>
  );
}
