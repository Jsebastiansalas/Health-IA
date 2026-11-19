import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, post } from "../api/cliente";
import type { Expediente, TipoExpediente } from "../api/tipos";
import { fecha, TIPOS_EXPEDIENTE } from "../lib/formato";
import { useSesion } from "../sesion";

const PERMISO: Record<string, string> = { ADMIN: "Administra", EDITOR: "Edita", LECTOR: "Consulta" };

export function PaginaExpedientes() {
  const { usuario } = useSesion();
  const { data: expedientes, isLoading, error } = useQuery({
    queryKey: ["expedientes"],
    queryFn: () => api<Expediente[]>("/expedientes?limit=200"),
  });
  const [filtro, setFiltro] = useState("");
  const [creando, setCreando] = useState(false);
  const puedeCrear = usuario && usuario.rol_global !== "LECTOR";

  const visibles = (expedientes ?? []).filter((e) =>
    `${e.codigo_expediente} ${e.titulo} ${e.entidad_contratante ?? ""}`.toLowerCase().includes(filtro.toLowerCase()),
  );

  return (
    <div className="animate-aparecer">
      <div className="mb-10 flex flex-wrap items-end justify-between gap-6 border-b-2 border-tinta pb-6">
        <div>
          <p className="etiqueta">Archivo</p>
          <h1 className="font-display text-5xl font-light">Expedientes</h1>
        </div>
        <div className="flex items-end gap-4">
          <label className="w-72">
            <span className="etiqueta">Buscar por código, título o entidad</span>
            <input className="campo" value={filtro} onChange={(e) => setFiltro(e.target.value)} />
          </label>
          {puedeCrear && (
            <button className="boton boton-tinta" onClick={() => setCreando((c) => !c)}>
              {creando ? "Cancelar" : "Abrir expediente"}
            </button>
          )}
        </div>
      </div>

      {creando && <NuevoExpediente alCrear={() => setCreando(false)} />}

      {isLoading && <p className="etiqueta">Cargando archivo…</p>}
      {error && <p className="text-sello">{(error as Error).message}</p>}
      {expedientes?.length === 0 && (
        <div className="folio max-w-xl p-10">
          <p className="font-display text-2xl">El archivo está vacío.</p>
          <p className="mt-2 text-tinta-2">
            {puedeCrear
              ? "Abra el primer expediente para empezar a indexar pliegos y adendas."
              : "Aún no le han dado acceso a ningún expediente."}
          </p>
        </div>
      )}

      <ol className="divide-y divide-papel-3">
        {visibles.map((e, i) => (
          <li key={e.id} className="animate-aparecer" style={{ animationDelay: `${Math.min(i, 12) * 40}ms` }}>
            <Link
              to={`/expedientes/${e.id}`}
              className="group grid grid-cols-[9rem_1fr_auto] items-baseline gap-6 py-5 transition-colors hover:bg-papel-2/60 md:grid-cols-[11rem_1fr_14rem_8rem]"
            >
              <span className="font-mono text-sm text-sello">{e.codigo_expediente}</span>
              <span>
                <span className="font-display text-2xl leading-tight group-hover:underline decoration-sello decoration-1 underline-offset-4">
                  {e.titulo}
                </span>
                <span className="mt-1 block text-sm text-tinta-2">
                  {e.entidad_contratante ?? "Entidad no registrada"} · {TIPOS_EXPEDIENTE[e.tipo_expediente]}
                </span>
              </span>
              <span className="hidden text-sm text-grafito md:block">
                {fecha(e.created_at)}
                <span className="block font-mono text-[0.7rem]">{e.embedding_model_activo}</span>
              </span>
              <span className="text-right">
                <span className={`sello ${e.estado === "ABIERTO" ? "text-clinico" : "text-grafito"}`}>{e.estado}</span>
                <span className="etiqueta mt-2 block">{e.mi_permiso ? PERMISO[e.mi_permiso] : ""}</span>
              </span>
            </Link>
          </li>
        ))}
      </ol>
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
    <form onSubmit={enviar} className="folio mb-10 grid animate-aparecer gap-6 p-8 md:grid-cols-4">
      <label>
        <span className="etiqueta">Código</span>
        <input className="campo font-mono" required maxLength={80} placeholder="LIC-2027-014"
          value={datos.codigo_expediente} onChange={cambiar("codigo_expediente")} />
      </label>
      <label className="md:col-span-2">
        <span className="etiqueta">Título</span>
        <input className="campo" required maxLength={250} value={datos.titulo} onChange={cambiar("titulo")} />
      </label>
      <label>
        <span className="etiqueta">Tipo</span>
        <select className="campo" value={datos.tipo_expediente} onChange={cambiar("tipo_expediente")}>
          {Object.entries(TIPOS_EXPEDIENTE).map(([v, t]) => (
            <option key={v} value={v}>{t}</option>
          ))}
        </select>
      </label>
      <label className="md:col-span-3">
        <span className="etiqueta">Entidad contratante</span>
        <input className="campo" maxLength={200} value={datos.entidad_contratante} onChange={cambiar("entidad_contratante")} />
      </label>
      <div className="flex items-end justify-end">
        <button className="boton boton-tinta" disabled={crear.isPending}>
          {crear.isPending ? "Abriendo…" : "Crear expediente"}
        </button>
      </div>
      {crear.error && <p className="text-sm text-sello md:col-span-4">{(crear.error as Error).message}</p>}
    </form>
  );
}
