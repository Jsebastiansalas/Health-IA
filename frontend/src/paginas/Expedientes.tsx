import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowUpRight, CalendarDays, ClipboardCheck, Cpu, FilePlus2, Pill, Search, Stethoscope } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api, post } from "../api/cliente";
import type { Expediente, TipoExpediente } from "../api/tipos";
import { Molecula } from "../arte/Decoracion";
import { Boton } from "../componentes/ui/Boton";
import { Campo } from "../componentes/ui/Campo";
import { Dialogo } from "../componentes/ui/Dialogo";
import { Esqueleto } from "../componentes/ui/Esqueleto";
import { Insignia } from "../componentes/ui/Insignia";
import { cn } from "../lib/cn";
import { fecha, TIPOS_EXPEDIENTE } from "../lib/formato";
import { useSesion } from "../sesion";

const PERMISO: Record<string, string> = { ADMIN: "Administras", EDITOR: "Editas", LECTOR: "Consultas" };
const ICONO_TIPO = {
  LICITACION_MEDICAMENTOS: Pill,
  DOTACION_BIOMEDICA: Stethoscope,
  AUDITORIA_CLINICA: ClipboardCheck,
} as const;
const FILTROS = [
  ["TODOS", "Todos"],
  ["ABIERTO", "Abiertos"],
  ["CERRADO", "Cerrados"],
  ["ARCHIVADO", "Archivados"],
] as const;

export function PaginaExpedientes() {
  const { usuario } = useSesion();
  const quieto = useReducedMotion();
  const { data: expedientes, isLoading, error, refetch } = useQuery({
    queryKey: ["expedientes"],
    queryFn: () => api<Expediente[]>("/expedientes?limit=200"),
  });
  const [filtro, setFiltro] = useState("");
  const [estado, setEstado] = useState<(typeof FILTROS)[number][0]>("TODOS");
  const [creando, setCreando] = useState(false);
  const buscador = useRef<HTMLInputElement>(null);
  const puedeCrear = !!usuario && usuario.rol_global !== "LECTOR";

  // Atajo: «/» enfoca el buscador (salvo que ya se esté escribiendo).
  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => {
      const destino = e.target as HTMLElement;
      if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(destino.tagName) && !destino.isContentEditable) {
        e.preventDefault();
        buscador.current?.focus();
      }
    };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, []);

  const visibles = (expedientes ?? []).filter(
    (e) =>
      (estado === "TODOS" || e.estado === estado) &&
      `${e.codigo_expediente} ${e.titulo} ${e.entidad_contratante ?? ""}`.toLowerCase().includes(filtro.toLowerCase()),
  );

  return (
    <div>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-5">
        <div>
          <h1 className="text-4xl font-semibold sm:text-5xl">Expedientes</h1>
          <p className="mt-2 text-tx-2">
            {usuario ? `Hola, ${usuario.nombre_completo.split(" ")[0]}. ` : ""}
            Elige un expediente para subir documentos o consultarlo.
          </p>
        </div>
        {puedeCrear && (
          <Boton variante="primario" tamano="lg" onClick={() => setCreando(true)}>
            <FilePlus2 className="size-[1.1rem]" aria-hidden />
            Abrir expediente
          </Boton>
        )}
      </div>

      <div className="mb-8 flex flex-wrap items-center gap-3">
        <div className="group flex h-11 w-full items-center gap-2.5 rounded-xl border border-ink/12 bg-white px-3.5 transition-[border-color,box-shadow] focus-within:border-hema/70 focus-within:shadow-[0_0_0_4px_rgb(75_63_201/0.12)] sm:w-80">
          <Search className="size-4 text-tx-3 group-focus-within:text-hema" aria-hidden />
          <input
            ref={buscador}
            value={filtro}
            onChange={(e) => setFiltro(e.target.value)}
            placeholder="Buscar por código, título o entidad"
            aria-label="Buscar expedientes"
            className="h-full min-w-0 flex-1 bg-transparent text-sm outline-none"
          />
          <kbd className="hidden rounded-md border border-ink/12 px-1.5 font-mono text-[0.7rem] text-tx-3 sm:block" aria-hidden>
            /
          </kbd>
        </div>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filtrar por estado">
          {FILTROS.map(([valor, texto]) => (
            <button
              key={valor}
              onClick={() => setEstado(valor)}
              aria-pressed={estado === valor}
              className={cn(
                "rounded-full border px-3.5 py-1.5 text-[0.82rem] font-semibold transition-colors",
                estado === valor
                  ? "border-hema/40 bg-hema/14 text-hema"
                  : "border-ink/10 text-tx-2 hover:border-ink/25 hover:text-tx",
              )}
            >
              {texto}
            </button>
          ))}
        </div>
      </div>

      {isLoading && (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3" aria-busy aria-label="Cargando expedientes">
          {[0, 1, 2].map((i) => (
            <Esqueleto key={i} className="h-56 rounded-3xl" />
          ))}
        </div>
      )}

      {error && (
        <div role="alert" className="vidrio flex max-w-xl items-start gap-4 rounded-3xl p-6">
          <AlertTriangle className="mt-0.5 size-6 shrink-0 text-coral" aria-hidden />
          <div>
            <p className="font-semibold">No pudimos cargar tus expedientes</p>
            <p className="mt-1 text-sm text-tx-2">{(error as Error).message}</p>
            <Boton className="mt-4" tamano="sm" onClick={() => refetch()}>
              Reintentar
            </Boton>
          </div>
        </div>
      )}

      {expedientes?.length === 0 && (
        <div className="vidrio relative max-w-2xl overflow-hidden rounded-3xl p-9">
          <Molecula className="absolute -right-6 -top-4 w-56 opacity-70" />
          <h2 className="relative max-w-sm text-3xl font-semibold">Aún no hay expedientes.</h2>
          <p className="relative mt-3 max-w-md text-tx-2">
            {puedeCrear
              ? "Abre el primero para empezar a indexar pliegos y adendas, y luego pregúntale lo que necesites."
              : "Todavía no te han dado acceso a ningún expediente. Pide a tu administrador que te asigne uno."}
          </p>
          {puedeCrear && (
            <Boton variante="primario" className="relative mt-6" onClick={() => setCreando(true)}>
              <FilePlus2 className="size-4" aria-hidden />
              Abrir el primer expediente
            </Boton>
          )}
        </div>
      )}

      {expedientes && expedientes.length > 0 && visibles.length === 0 && (
        <p className="py-10 text-tx-2">
          Ningún expediente coincide con «{filtro}»
          {estado !== "TODOS" ? ` en estado ${estado.toLowerCase()}` : ""}.
        </p>
      )}

      <ul className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {visibles.map((e, i) => {
          const Icono = ICONO_TIPO[e.tipo_expediente];
          return (
            <motion.li
              key={e.id}
              initial={quieto ? false : { opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.55, delay: Math.min(i, 9) * 0.05, ease: [0.16, 1, 0.3, 1] }}
            >
              <Link
                to={`/expedientes/${e.id}`}
                className="vidrio group relative flex h-full flex-col overflow-hidden rounded-3xl p-6 transition-[transform,border-color,box-shadow] duration-300 ease-[var(--ease-salida)] hover:-translate-y-1 hover:border-hema/35 hover:shadow-[0_30px_60px_-28px_rgb(75_63_201/0.35)]"
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="grid size-12 place-items-center rounded-2xl border border-hema/25 bg-hema/10 text-hema">
                    <Icono className="size-6" strokeWidth={1.6} aria-hidden />
                  </span>
                  <Insignia tono={e.estado === "ABIERTO" ? "hema" : "neutro"}>{e.estado}</Insignia>
                </div>
                <p className="mt-5 font-mono text-[0.78rem] text-hema">{e.codigo_expediente}</p>
                <h2 className="mt-1 text-[1.35rem] font-semibold leading-tight tracking-tight">{e.titulo}</h2>
                <p className="mt-2 text-sm text-tx-2">
                  {e.entidad_contratante ?? "Entidad no registrada"} · {TIPOS_EXPEDIENTE[e.tipo_expediente]}
                </p>
                <div className="mt-auto flex items-center justify-between gap-3 border-t border-ink/8 pt-4 text-[0.78rem] text-tx-3">
                  <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="inline-flex items-center gap-1.5">
                      <CalendarDays className="size-3.5" aria-hidden />
                      {fecha(e.created_at)}
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <Cpu className="size-3.5" aria-hidden />
                      <span className="font-mono">{e.embedding_model_activo}</span>
                    </span>
                  </span>
                  <span className="inline-flex items-center gap-1 font-semibold text-tx-2 transition-colors group-hover:text-hema">
                    {e.mi_permiso ? PERMISO[e.mi_permiso] : ""}
                    <ArrowUpRight className="size-4" aria-hidden />
                  </span>
                </div>
              </Link>
            </motion.li>
          );
        })}
      </ul>

      <Dialogo
        abierto={creando}
        alCambiar={setCreando}
        titulo="Abrir expediente"
        descripcion="Un expediente agrupa los documentos de un proceso y sus consultas."
      >
        <NuevoExpediente alCrear={() => setCreando(false)} />
      </Dialogo>
    </div>
  );
}

function NuevoExpediente({ alCrear }: { alCrear: () => void }) {
  const cliente = useQueryClient();
  const navegar = useNavigate();
  const [datos, setDatos] = useState({
    codigo_expediente: "",
    titulo: "",
    entidad_contratante: "",
    tipo_expediente: "LICITACION_MEDICAMENTOS" as TipoExpediente,
  });
  const crear = useMutation({
    mutationFn: () => post<Expediente>("/expedientes", { ...datos, entidad_contratante: datos.entidad_contratante || null }),
    onSuccess: (e) => {
      cliente.invalidateQueries({ queryKey: ["expedientes"] });
      toast.success("Expediente creado", { description: e.codigo_expediente });
      alCrear();
      navegar(`/expedientes/${e.id}`);
    },
  });
  const cambiar = (campo: keyof typeof datos) => (ev: { target: { value: string } }) =>
    setDatos((d) => ({ ...d, [campo]: ev.target.value }));

  function enviar(e: FormEvent) {
    e.preventDefault();
    crear.mutate();
  }

  return (
    <form onSubmit={enviar} className="space-y-5">
      <Campo etiqueta="Código" required maxLength={80} placeholder="LIC-2027-014" className="[&_input]:font-mono"
        value={datos.codigo_expediente} onChange={cambiar("codigo_expediente")} autoFocus />
      <Campo etiqueta="Título" required maxLength={250} placeholder="Suministro de medicamentos oncológicos"
        value={datos.titulo} onChange={cambiar("titulo")} />
      <div>
        <label htmlFor="tipo-expediente" className="mb-1.5 block text-[0.8rem] font-medium text-tx-2">
          Tipo de expediente
        </label>
        <select
          id="tipo-expediente"
          value={datos.tipo_expediente}
          onChange={cambiar("tipo_expediente")}
          className="h-12 w-full rounded-xl border border-ink/12 bg-white px-3.5 text-[0.95rem] outline-none transition-[border-color,box-shadow] focus:border-hema/70 focus:shadow-[0_0_0_4px_rgb(75_63_201/0.12)]"
        >
          {Object.entries(TIPOS_EXPEDIENTE).map(([v, t]) => (
            <option key={v} value={v} className="bg-white">
              {t}
            </option>
          ))}
        </select>
      </div>
      <Campo etiqueta="Entidad contratante" maxLength={200} placeholder="Hospital Universitario"
        value={datos.entidad_contratante} onChange={cambiar("entidad_contratante")} />
      {crear.error && (
        <p role="alert" className="rounded-xl border border-coral/35 bg-coral/10 px-3.5 py-3 text-sm text-[#b3202f]">
          {(crear.error as Error).message}
        </p>
      )}
      <Boton type="submit" variante="primario" tamano="lg" className="w-full" cargando={crear.isPending}>
        {crear.isPending ? "Abriendo…" : "Crear expediente"}
      </Boton>
    </form>
  );
}
