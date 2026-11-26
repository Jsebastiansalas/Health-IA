import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, post } from "../api/cliente";
import type { CompartidoConmigo, Comparticion } from "../api/tipos";
import { ChevronRight, ShareNetwork, UsersThree } from "../iconos";
import { Boton } from "./ui/Boton";
import { Campo } from "./ui/Campo";
import { Dialogo } from "./ui/Dialogo";
import { Insignia } from "./ui/Insignia";

const FECHA = new Intl.DateTimeFormat("es-CO", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

const OPCIONES = [
  ["LECTOR", "Solo ver y preguntar", "Verá los documentos, la línea de tiempo y las explicaciones, y podrá preguntar."],
  ["EDITOR", "Ver y subir documentos", "Además podrá cargar documentos nuevos a este expediente."],
] as const;

function estadoDe(c: Comparticion) {
  if (c.estado === "PENDIENTE") return "Invitación sin aceptar";
  return c.ultimo_acceso ? `Entró por última vez el ${FECHA.format(new Date(c.ultimo_acceso))}` : "Aún no ha entrado";
}

/** La dueña invita a un cuidador a ESTE expediente, ve quién tiene acceso y lo quita. */
export function CompartirExpediente({ expedienteId }: { expedienteId: string }) {
  const [abierto, setAbierto] = useState(false);
  return (
    <>
      <Boton variante="secundario" tamano="sm" onClick={() => setAbierto(true)}>
        <ShareNetwork className="size-4" aria-hidden />
        Compartir con un cuidador
      </Boton>
      <Dialogo
        abierto={abierto}
        alCambiar={setAbierto}
        titulo="Compartir con un cuidador"
        descripcion="Solo este expediente. Puedes quitar el acceso cuando quieras."
      >
        {abierto && <Panel expedienteId={expedienteId} />}
      </Dialogo>
    </>
  );
}

function Panel({ expedienteId }: { expedienteId: string }) {
  const cliente = useQueryClient();
  const [correo, setCorreo] = useState("");
  const [permiso, setPermiso] = useState<"LECTOR" | "EDITOR">("LECTOR");
  const [confirmado, setConfirmado] = useState(false);
  const base = `/expedientes/${expedienteId}/comparticiones`;
  const clave = ["comparticiones", expedienteId];
  const { data: lista } = useQuery({ queryKey: clave, queryFn: () => api<Comparticion[]>(base) });
  const invitar = useMutation({
    mutationFn: () => post<Comparticion>(base, { correo: correo.trim(), permiso }),
    onSuccess: () => {
      setCorreo("");
      setConfirmado(false);
      void cliente.invalidateQueries({ queryKey: clave });
    },
  });
  const quitar = useMutation({
    mutationFn: (id: string) => api<void>(`${base}/${id}`, { method: "DELETE" }),
    onSuccess: () => void cliente.invalidateQueries({ queryKey: clave }),
  });
  function enviar(e: FormEvent) {
    e.preventDefault();
    invitar.mutate();
  }
  const error = (invitar.error ?? quitar.error) as Error | null;

  return (
    <div className="space-y-6">
      <form onSubmit={enviar} className="space-y-4">
        <Campo
          etiqueta="Correo de esa persona"
          type="email"
          required
          maxLength={150}
          autoComplete="off"
          value={correo}
          onChange={(e) => setCorreo(e.target.value)}
        />
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-texto-2">Qué podrá hacer</legend>
          <div className="space-y-2">
            {OPCIONES.map(([valor, nombre, detalle]) => (
              <label key={valor} className="flex cursor-pointer gap-3 rounded-lg border border-borde p-3 has-checked:border-primario">
                <input type="radio" name="permiso" className="mt-1" checked={permiso === valor} onChange={() => setPermiso(valor)} />
                <span>
                  <span className="block text-sm font-semibold">{nombre}</span>
                  <span className="block text-sm text-texto-2">{detalle}</span>
                </span>
              </label>
            ))}
          </div>
          <p className="mt-2 text-sm text-texto-2">
            En ningún caso podrá borrar documentos, el historial ni el expediente, ni compartirlo con nadie más.
          </p>
        </fieldset>
        <label className="flex cursor-pointer gap-3 text-sm leading-relaxed">
          <input type="checkbox" className="mt-1" checked={confirmado} onChange={(e) => setConfirmado(e.target.checked)} />
          <span>
            Tengo derecho a compartir esta información de salud (es mía o tengo autorización) y entiendo que esa persona
            verá todos los documentos de este expediente.
          </span>
        </label>
        {error && (
          <p role="alert" className="rounded-xl border border-peligro/35 bg-peligro/10 px-4 py-3 text-sm text-peligro">
            {error.message}
          </p>
        )}
        {invitar.isSuccess && (
          <p role="status" className="text-sm text-ok">
            Invitación enviada. Vale 7 días.
          </p>
        )}
        <Boton type="submit" variante="primario" className="w-full" disabled={!correo.trim() || !confirmado} cargando={invitar.isPending}>
          Enviar invitación
        </Boton>
      </form>

      {lista && lista.length > 0 && (
        <section aria-labelledby="titulo-con-acceso">
          <h3 id="titulo-con-acceso" className="mb-2 text-sm font-medium text-texto-2">
            Con acceso o invitadas
          </h3>
          <ul className="divide-y divide-borde border-y border-borde">
            {lista.map((c) => (
              <li key={c.id} className="flex items-start justify-between gap-3 py-3">
                <span className="min-w-0">
                  <span className="block text-sm font-semibold [overflow-wrap:anywhere]">{c.correo}</span>
                  <span className="block text-sm text-texto-2">
                    {c.permiso === "EDITOR" ? "Ve y sube" : "Solo ve"} · {estadoDe(c)}
                  </span>
                </span>
                <Boton
                  variante="peligro"
                  tamano="sm"
                  aria-label={`Quitar acceso a ${c.correo}`}
                  onClick={() => quitar.mutate(c.id)}
                  cargando={quitar.isPending && quitar.variables === c.id}
                >
                  Quitar
                </Boton>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

/** Lo que otras personas comparten con quien está viendo la lista. */
export function CompartidosConmigo() {
  const { data } = useQuery({ queryKey: ["compartidos"], queryFn: () => api<CompartidoConmigo[]>("/compartidos") });
  if (!data?.length) return null;
  return (
    <section aria-labelledby="titulo-compartidos" className="mb-8">
      <h2 id="titulo-compartidos" className="mb-3 flex items-center gap-2 text-xl font-semibold">
        <UsersThree className="size-5 text-primario" aria-hidden />
        Compartidos contigo
      </h2>
      <ul className="panel divide-y divide-borde overflow-hidden">
        {data.map((c) => (
          <li key={c.expediente_id}>
            <Link to={`/expedientes/${c.expediente_id}`} className="group flex items-center gap-3 px-4 py-4 transition-colors hover:bg-panel-2">
              <span className="min-w-0 flex-1">
                <span className="block text-base font-semibold [overflow-wrap:anywhere] group-hover:text-primario">{c.titulo}</span>
                <span className="block text-sm text-texto-2">De {c.compartido_por}</span>
              </span>
              <Insignia>{c.permiso === "EDITOR" ? "Ver y subir" : "Solo ver"}</Insignia>
              <ChevronRight className="size-4 text-texto-3" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Dentro de un expediente ajeno: de quién es, qué se puede hacer y cómo dejar de verlo. */
export function AvisoCompartido({ expedienteId, por, puedeSubir }: { expedienteId: string; por: string; puedeSubir: boolean }) {
  const cliente = useQueryClient();
  const navegar = useNavigate();
  const [confirmando, setConfirmando] = useState(false);
  const salir = useMutation({
    mutationFn: () => api<void>(`/compartidos/${expedienteId}`, { method: "DELETE" }),
    onSuccess: () => {
      cliente.removeQueries({ queryKey: ["expediente", expedienteId] });
      cliente.removeQueries({ queryKey: ["documentos", expedienteId] });
      cliente.removeQueries({ queryKey: ["consultas", expedienteId] });
      void cliente.invalidateQueries({ queryKey: ["compartidos"] });
      navegar("/");
    },
  });
  return (
    <div role="note" className="panel mb-6 flex flex-wrap items-center justify-between gap-4 p-4">
      <p className="max-w-2xl text-sm leading-relaxed">
        <strong>{por} te compartió este expediente.</strong>{" "}
        {puedeSubir ? "Puedes ver, preguntar y subir documentos." : "Puedes ver y preguntar."} Trata esta información como
        privada. {por} puede ver cuándo entras.
      </p>
      {salir.error && (
        <p role="alert" className="text-sm text-peligro">
          {(salir.error as Error).message}
        </p>
      )}
      {confirmando ? (
        <span className="flex gap-2">
          <Boton variante="secundario" tamano="sm" onClick={() => setConfirmando(false)}>
            Cancelar
          </Boton>
          <Boton variante="peligro" tamano="sm" onClick={() => salir.mutate()} cargando={salir.isPending}>
            Sí, dejar de verlo
          </Boton>
        </span>
      ) : (
        <Boton variante="fantasma" tamano="sm" onClick={() => setConfirmando(true)}>
          Dejar de ver
        </Boton>
      )}
    </div>
  );
}
