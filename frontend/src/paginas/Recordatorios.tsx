import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { api, descargar } from "../api/cliente";
import { AvisosEnDispositivo } from "../componentes/AvisosEnDispositivo";
import type { EstadoRecordatorio, Recordatorio } from "../api/tipos";
import { Boton } from "../componentes/ui/Boton";
import { Esqueleto } from "../componentes/ui/Esqueleto";
import { Insignia } from "../componentes/ui/Insignia";
import { Bell, CalendarPlus, Check, FileText, X } from "../iconos";

const CLAVE = ["recordatorios"];

const fmtFecha = (iso: string | null) =>
  iso ? new Date(`${iso}T12:00:00`).toLocaleDateString("es-CO", { weekday: "long", day: "numeric", month: "long", year: "numeric" }) : "";
const hoyIso = () => new Date().toLocaleDateString("en-CA");

/** Cambiar el estado (y la fecha) de un recordatorio; actualiza la lista sin volver a pedirla. */
function useCambiar() {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: ({ id, estado, fecha }: { id: string; estado: EstadoRecordatorio; fecha?: string | null }) =>
      api<Recordatorio>(`/recordatorios/${id}`, { method: "PATCH", body: JSON.stringify({ estado, fecha: fecha || null }) }),
    onSuccess: (r) =>
      cliente.setQueryData<Recordatorio[]>(CLAVE, (lista) =>
        (lista ?? []).map((x) => (x.id === r.id ? r : x)).filter((x) => x.estado !== "DESCARTADO"),
      ),
    onError: (e) => toast.error((e as Error).message),
  });
}

/**
 * Recordatorios de los controles que indican tus documentos. MedTender solo los propone: tú confirmas cada uno
 * (y su fecha) antes de que te avisemos. El aviso por correo y el evento de calendario no llevan datos de salud.
 */
export function PaginaRecordatorios() {
  const { data, isLoading, error } = useQuery({ queryKey: CLAVE, queryFn: () => api<Recordatorio[]>("/recordatorios") });
  const lista = data ?? [];
  const propuestos = lista.filter((r) => r.estado === "PROPUESTO");
  const confirmados = lista.filter((r) => r.estado === "CONFIRMADO");
  const hechos = lista.filter((r) => r.estado === "HECHO");

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header>
        <h1 className="flex items-center gap-3 text-3xl font-semibold">
          <Bell className="size-7 text-primario" aria-hidden />
          Recordatorios
        </h1>
        <p className="mt-2 text-base text-texto-2">
          Los controles que indican tus documentos. Confirma la fecha de cada uno y te avisamos por correo unos días antes. Para
          buscar nuevos, abre un expediente y pulsa «Buscar controles en mis documentos».
        </p>
        <p className="mt-2 text-sm text-texto-3">
          No creamos recordatorios para tomar medicamentos: cómo y cuándo tomarlos lo indica tu médico.
        </p>
      </header>

      <AvisosEnDispositivo />

      {isLoading && <Esqueleto className="h-40 rounded-xl" aria-busy />}
      {error && (
        <p role="alert" className="text-peligro">
          {(error as Error).message}
        </p>
      )}
      {!isLoading && !error && lista.length === 0 && (
        <p className="rounded-xl border border-dashed border-borde p-6 text-sm text-texto-2">
          Aún no tienes recordatorios. Desde un expediente con documentos leídos, pulsa «Buscar controles en mis documentos».
        </p>
      )}

      {propuestos.length > 0 && (
        <Seccion titulo="Por confirmar" descripcion="Revisa la fecha: la calculamos con lo que escribe el documento.">
          {propuestos.map((r) => (
            <TarjetaPropuesta key={r.id} r={r} />
          ))}
        </Seccion>
      )}
      {confirmados.length > 0 && (
        <Seccion titulo="Próximos" descripcion="Te avisamos por correo unos días antes.">
          {confirmados.map((r) => (
            <TarjetaConfirmado key={r.id} r={r} />
          ))}
        </Seccion>
      )}
      {hechos.length > 0 && (
        <Seccion titulo="Hechos">
          {hechos.map((r) => (
            <li key={r.id} className="panel flex items-center justify-between gap-3 p-4 text-sm text-texto-2">
              <span>
                {r.texto} · {fmtFecha(r.fecha)}
              </span>
              <Insignia tono="ok">
                <Check className="size-4" aria-hidden />
                Hecho
              </Insignia>
            </li>
          ))}
        </Seccion>
      )}
    </div>
  );
}

function Seccion({ titulo, descripcion, children }: { titulo: string; descripcion?: string; children: React.ReactNode }) {
  return (
    <section aria-label={titulo}>
      <h2 className="text-xl font-semibold">{titulo}</h2>
      {descripcion && <p className="mt-1 text-sm text-texto-3">{descripcion}</p>}
      <ul className="mt-4 space-y-3">{children}</ul>
    </section>
  );
}

function Fuente({ r }: { r: Recordatorio }) {
  return (
    <p className="mt-2 flex items-start gap-2 text-xs text-texto-3">
      <FileText className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>
        Según {r.cita.nombreArchivo ?? "tu documento"}
        {r.cita.paginaInicio ? `, pág. ${r.cita.paginaInicio}` : ""}
        {r.cita.extractoLiteral && (
          <>
            : <span className="resaltado">«{r.cita.extractoLiteral}»</span>
          </>
        )}
        {r.fecha_documento && ` · documento del ${fmtFecha(r.fecha_documento)}`}
      </span>
    </p>
  );
}

function TarjetaPropuesta({ r }: { r: Recordatorio }) {
  const cambiar = useCambiar();
  const [fecha, setFecha] = useState(r.fecha_propuesta ?? "");
  const pasada = !!fecha && fecha < hoyIso();
  return (
    <li className="panel p-4">
      <p className="font-medium text-texto">{r.texto}</p>
      <Fuente r={r} />
      <div className="mt-4 flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block text-xs font-medium text-texto-2">Fecha del control</span>
          <input
            type="date"
            value={fecha}
            onChange={(e) => setFecha(e.target.value)}
            className="h-10 rounded-lg border border-borde bg-panel px-3 outline-none focus:border-texto"
          />
        </label>
        <Boton
          variante="primario"
          disabled={!fecha}
          cargando={cambiar.isPending && cambiar.variables?.estado === "CONFIRMADO"}
          onClick={() => cambiar.mutate({ id: r.id, estado: "CONFIRMADO", fecha })}
        >
          Confirmar
        </Boton>
        <Boton variante="fantasma" onClick={() => cambiar.mutate({ id: r.id, estado: "DESCARTADO" })}>
          <X className="size-4" aria-hidden />
          Descartar
        </Boton>
      </div>
      {!r.fecha_propuesta && <p className="mt-2 text-xs text-texto-3">El documento no dice cuándo: pon tú la fecha.</p>}
      {pasada && <p className="mt-2 text-xs text-aviso">Esa fecha ya pasó. Si el control sigue pendiente, pide una cita nueva.</p>}
    </li>
  );
}

function TarjetaConfirmado({ r }: { r: Recordatorio }) {
  const cambiar = useCambiar();
  const [editando, setEditando] = useState(false);
  const [fecha, setFecha] = useState(r.fecha ?? "");

  async function alCalendario() {
    try {
      const blob = await descargar(`/recordatorios/${r.id}/calendario.ics`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "control-medico.ics";
      a.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <li className="panel p-4">
      <p className="flex flex-wrap items-center gap-2">
        <span className="num font-semibold text-texto first-letter:uppercase">{fmtFecha(r.fecha)}</span>
        {r.avisado && <Insignia>Aviso enviado</Insignia>}
      </p>
      <p className="mt-1 text-texto">{r.texto}</p>
      <Fuente r={r} />
      {editando ? (
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <input
            type="date"
            value={fecha}
            aria-label="Nueva fecha del control"
            onChange={(e) => setFecha(e.target.value)}
            className="h-10 rounded-lg border border-borde bg-panel px-3 outline-none focus:border-texto"
          />
          <Boton
            variante="primario"
            disabled={!fecha}
            onClick={() => cambiar.mutate({ id: r.id, estado: "CONFIRMADO", fecha }, { onSuccess: () => setEditando(false) })}
          >
            Guardar
          </Boton>
          <Boton variante="fantasma" onClick={() => setEditando(false)}>
            Cancelar
          </Boton>
        </div>
      ) : (
        <div className="mt-4 flex flex-wrap gap-2">
          <Boton variante="secundario" tamano="sm" onClick={() => void alCalendario()}>
            <CalendarPlus className="size-4" aria-hidden />
            Añadir a mi calendario
          </Boton>
          <Boton variante="secundario" tamano="sm" onClick={() => cambiar.mutate({ id: r.id, estado: "HECHO" })}>
            <Check className="size-4" aria-hidden />
            Ya fui
          </Boton>
          <Boton variante="fantasma" tamano="sm" onClick={() => setEditando(true)}>
            Cambiar fecha
          </Boton>
          <Boton variante="fantasma" tamano="sm" onClick={() => cambiar.mutate({ id: r.id, estado: "DESCARTADO" })}>
            Quitar
          </Boton>
        </div>
      )}
    </li>
  );
}
