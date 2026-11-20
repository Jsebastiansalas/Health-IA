import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, FilePlus2, Search } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api, post } from "../api/cliente";
import type { Expediente, TipoExpediente } from "../api/tipos";
import { Boton } from "../componentes/ui/Boton";
import { Campo } from "../componentes/ui/Campo";
import { Dialogo } from "../componentes/ui/Dialogo";
import { Esqueleto } from "../componentes/ui/Esqueleto";
import { Insignia } from "../componentes/ui/Insignia";
import { cn } from "../lib/cn";
import { TIPOS_EXPEDIENTE } from "../lib/formato";
import { useSesion } from "../sesion";

/** Día sin hora: en un índice importa cuándo se abrió, no a qué minuto. */
const dia = (iso: string) =>
  new Date(iso).toLocaleDateString("es-CO", { day: "2-digit", month: "short", year: "numeric" });

const PERMISO: Record<string, string> = { ADMIN: "Administras", EDITOR: "Editas", LECTOR: "Consultas" };
const FILTROS = [
  ["TODOS", "Todos"],
  ["ABIERTO", "Abiertos"],
  ["CERRADO", "Cerrados"],
  ["ARCHIVADO", "Archivados"],
] as const;

export function PaginaExpedientes() {
  const { usuario } = useSesion();
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
          <h1 className="text-3xl font-semibold sm:text-4xl">Expedientes</h1>
          <p className="mt-2 text-tinta-2">
            {usuario ? `Hola, ${usuario.nombre_completo.split(" ")[0]}. ` : ""}
            Elige un expediente para subir documentos o consultarlo.
          </p>
        </div>
        {puedeCrear && (
          <Boton variante="primario" onClick={() => setCreando(true)}>
            <FilePlus2 className="size-[1.1rem]" aria-hidden />
            Abrir expediente
          </Boton>
        )}
      </div>

      <div className="mb-8 flex flex-wrap items-center gap-3">
        <div className="group flex h-11 w-full items-center gap-2.5 rounded-md border border-tinta/35 bg-folio px-3 transition-[border-color] focus-within:border-accion sm:w-96">
          <Search className="size-4 text-tinta-3 group-focus-within:text-accion" aria-hidden />
          <input
            ref={buscador}
            value={filtro}
            onChange={(e) => setFiltro(e.target.value)}
            placeholder="Buscar por código, título o entidad"
            aria-label="Buscar expedientes"
            className="h-full min-w-0 flex-1 bg-transparent text-sm outline-none"
          />
          <kbd className="hidden rounded-md border border-tinta/12 px-1.5 font-mono text-[0.7rem] text-tinta-3 sm:block" aria-hidden>
            /
          </kbd>
        </div>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filtrar por estado">
          {FILTROS.map(([valor, texto]) => {
            const n = (expedientes ?? []).filter((e) => valor === "TODOS" || e.estado === valor).length;
            return (
              <button
                key={valor}
                onClick={() => setEstado(valor)}
                aria-pressed={estado === valor}
                className={cn(
                  "rounded-md border px-3 py-1.5 text-[0.82rem] font-medium transition-colors",
                  estado === valor
                    ? "border-accion/50 bg-accion/12 text-accion"
                    : "border-tinta/15 text-tinta-2 hover:border-tinta/35 hover:text-tinta",
                )}
              >
                {texto}
                {expedientes && <span className="num ml-1.5 text-tinta-3">{n}</span>}
              </button>
            );
          })}
        </div>
      </div>

      {isLoading && (
        <div className="folio divide-y divide-tinta/10" aria-busy aria-label="Cargando expedientes">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="px-5 py-4">
              <Esqueleto className="h-5 w-2/3" />
              <Esqueleto className="mt-2 h-3.5 w-1/3" />
            </div>
          ))}
        </div>
      )}

      {error && (
        <div role="alert" className="folio flex max-w-xl items-start gap-4 p-6">
          <AlertTriangle className="mt-0.5 size-6 shrink-0 text-peligro" aria-hidden />
          <div>
            <p className="font-semibold">No pudimos cargar tus expedientes</p>
            <p className="mt-1 text-sm text-tinta-2">{(error as Error).message}</p>
            <Boton className="mt-4" tamano="sm" onClick={() => refetch()}>
              Reintentar
            </Boton>
          </div>
        </div>
      )}

      {expedientes?.length === 0 && (
        <div className="max-w-2xl py-6">
          <h2 className="max-w-sm text-3xl font-semibold">Aún no hay expedientes.</h2>
          <p className="relative mt-3 max-w-md text-tinta-2">
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
        <p className="py-10 text-tinta-2">
          Ningún expediente coincide con «{filtro}»
          {estado !== "TODOS" ? ` en estado ${estado.toLowerCase()}` : ""}.
        </p>
      )}

      {visibles.length > 0 && (
        <div className="folio overflow-hidden">
          <div
            className="hidden grid-cols-[8.5rem_minmax(0,1fr)_9rem_6.5rem_7.5rem] gap-x-4 border-b border-tinta/15 px-5 py-2.5 text-[0.74rem] font-medium text-tinta-3 md:grid"
            aria-hidden
          >
            <span>Código</span>
            <span>Expediente</span>
            <span>Tipo</span>
            <span>Estado</span>
            <span className="text-right">Creado</span>
          </div>
          <ul className="divide-y divide-tinta/10">
            {visibles.map((e) => (
              <li key={e.id}>
                <Link
                  to={`/expedientes/${e.id}`}
                  className="group grid gap-x-4 gap-y-1 px-5 py-4 transition-colors hover:bg-folio-2 focus-visible:bg-folio-2 md:grid-cols-[8.5rem_minmax(0,1fr)_9rem_6.5rem_7.5rem] md:items-center"
                >
                  <span className="font-mono text-[0.82rem] text-tinta">{e.codigo_expediente}</span>
                  <span className="min-w-0">
                    <span className="block font-display text-[1.1rem] font-semibold leading-snug group-hover:text-accion">
                      {e.titulo}
                    </span>
                    <span className="mt-0.5 block truncate text-[0.82rem] text-tinta-2">
                      {e.entidad_contratante ?? "Entidad no registrada"}
                      {e.mi_permiso ? ` · ${PERMISO[e.mi_permiso]}` : ""}
                    </span>
                  </span>
                  <span className="text-[0.82rem] text-tinta-2">{TIPOS_EXPEDIENTE[e.tipo_expediente]}</span>
                  <span>
                    <Insignia tono={e.estado === "ABIERTO" ? "accion" : "neutro"}>{e.estado}</Insignia>
                  </span>
                  <span className="num text-[0.8rem] text-tinta-3 md:text-right">{dia(e.created_at)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

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
        <label htmlFor="tipo-expediente" className="mb-1.5 block text-[0.85rem] font-medium text-tinta-2">
          Tipo de expediente
        </label>
        <select
          id="tipo-expediente"
          value={datos.tipo_expediente}
          onChange={cambiar("tipo_expediente")}
          className="h-11 w-full rounded-md border border-tinta/35 bg-folio px-3 text-[0.95rem] outline-none transition-[border-color,box-shadow] focus:border-accion focus:shadow-[0_0_0_3px_color-mix(in_oklab,var(--accion)_22%,transparent)]"
        >
          {Object.entries(TIPOS_EXPEDIENTE).map(([v, t]) => (
            <option key={v} value={v} className="bg-folio">
              {t}
            </option>
          ))}
        </select>
      </div>
      <Campo etiqueta="Entidad contratante" maxLength={200} placeholder="Hospital Universitario"
        value={datos.entidad_contratante} onChange={cambiar("entidad_contratante")} />
      {crear.error && (
        <p role="alert" className="rounded-xl border border-peligro/35 bg-peligro/10 px-3.5 py-3 text-sm text-peligro">
          {(crear.error as Error).message}
        </p>
      )}
      <Boton type="submit" variante="primario" tamano="lg" className="w-full" cargando={crear.isPending}>
        {crear.isPending ? "Abriendo…" : "Crear expediente"}
      </Boton>
    </form>
  );
}
