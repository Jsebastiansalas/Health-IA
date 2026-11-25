import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";
import { api, descargar } from "../api/cliente";
import { Boton } from "../componentes/ui/Boton";
import { Campo } from "../componentes/ui/Campo";
import { DownloadSimple, FileText, ShieldCheck } from "../iconos";

interface Retencion {
  meses: number | null;
  /** Cuántas respuestas guardadas se borrarían hoy con cada plazo. */
  se_borrarian: Record<string, number>;
}

const OPCIONES: { valor: number | null; texto: string }[] = [
  { valor: null, texto: "Conservar todo" },
  { valor: 24, texto: "24 meses" },
  { valor: 12, texto: "12 meses" },
  { valor: 6, texto: "6 meses" },
  { valor: 3, texto: "3 meses" },
];

const mensaje = (e: unknown) => (e instanceof Error ? e.message : "No se pudo completar");

function Seccion({ id, titulo, icono: Icono, children }: { id: string; titulo: string; icono: typeof FileText; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="panel p-6">
      <h2 id={id} className="flex items-center gap-2 text-xl font-semibold">
        <Icono className="size-5 text-primario" aria-hidden />
        {titulo}
      </h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

/** Derechos sobre los datos: llevarse una copia y decidir cuánto se guarda el historial. */
export function PaginaMisDatos() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header>
        <h1 className="flex items-center gap-3 text-3xl font-semibold">
          <ShieldCheck className="size-7 text-primario" aria-hidden />
          Mis datos
        </h1>
        <p className="mt-2 text-texto-2">
          Son tuyos: puedes llevarte una copia y decidir cuánto guardamos. Para borrar todo, usa «Eliminar mi cuenta» en el menú.
        </p>
      </header>
      <Descarga />
      <Historial />
    </div>
  );
}

function Descarga() {
  const [password, setPassword] = useState("");
  const bajar = useMutation({
    mutationFn: () => descargar("/cuenta/exportar", { password }),
    onSuccess: (archivo) => {
      const url = URL.createObjectURL(archivo);
      const enlace = document.createElement("a");
      enlace.href = url;
      enlace.download = `medtender-mis-datos-${new Date().toLocaleDateString("en-CA")}.zip`;
      enlace.click();
      URL.revokeObjectURL(url);
      setPassword("");
      toast.success("Tu copia se descargó");
    },
  });
  return (
    <Seccion id="sec-descarga" titulo="Descargar una copia" icono={DownloadSimple}>
      <p className="text-sm text-texto-2">
        Un archivo ZIP con tu cuenta, el texto leído de tus documentos, tus preguntas y respuestas, tus recordatorios, tus consentimientos y el
        registro de accesos. Trae una versión para leer y otra en JSON. No incluye los archivos originales, que se borran después de leerlos.
      </p>
      <p className="mt-2 text-sm text-aviso">Contiene información de salud: guárdalo en un lugar seguro y no lo dejes en un equipo compartido.</p>
      <form
        className="mt-4 flex flex-wrap items-end gap-3"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          bajar.mutate();
        }}
      >
        <Campo etiqueta="Contraseña" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <Boton type="submit" variante="primario" cargando={bajar.isPending} disabled={!password}>
          Descargar mis datos
        </Boton>
      </form>
      {bajar.error && (
        <p role="alert" className="mt-3 text-sm text-peligro">
          {mensaje(bajar.error)}
        </p>
      )}
    </Seccion>
  );
}

function Historial() {
  const cliente = useQueryClient();
  const { data, error } = useQuery({ queryKey: ["retencion"], queryFn: () => api<Retencion>("/cuenta/retencion") });
  // `undefined`: sin cambios pendientes. `null` es una elección válida (conservar todo).
  const [elegido, setElegido] = useState<number | null | undefined>(undefined);
  const guardar = useMutation({
    mutationFn: (meses: number | null) =>
      api<{ meses: number | null; borradas: number }>("/cuenta/retencion", { method: "PUT", body: JSON.stringify({ meses }) }),
    onSuccess: async (r) => {
      await cliente.invalidateQueries({ queryKey: ["retencion"] });
      setElegido(undefined);
      toast.success("Preferencia guardada", r.borradas ? { description: `Se borraron ${r.borradas} respuestas guardadas.` } : undefined);
    },
  });

  const actual = data?.meses ?? null;
  const marcado = elegido === undefined ? actual : elegido;
  const pendiente = elegido !== undefined && elegido !== actual;
  const seBorran = pendiente && elegido ? (data?.se_borrarian[String(elegido)] ?? 0) : 0;

  return (
    <Seccion id="sec-historial" titulo="Cuánto guardamos tu historial" icono={FileText}>
      <p className="text-sm text-texto-2">
        Incluye tus preguntas y respuestas, las explicaciones y las líneas de tiempo guardadas. Tus documentos, expedientes y recordatorios no se
        borran.
      </p>
      {error && (
        <p role="alert" className="mt-3 text-sm text-peligro">
          {mensaje(error)}
        </p>
      )}
      {data && (
        <fieldset className="mt-4 space-y-2">
          <legend className="sr-only">Plazo del historial</legend>
          {OPCIONES.map((o) => (
            <label key={o.texto} className="flex items-center gap-3 text-sm">
              <input type="radio" name="retencion" checked={marcado === o.valor} onChange={() => setElegido(o.valor)} />
              {o.texto}
            </label>
          ))}
        </fieldset>
      )}
      {pendiente && (
        <div className="mt-4 space-y-3">
          <p role="status" className={seBorran ? "text-sm font-medium text-peligro" : "text-sm text-texto-2"}>
            {seBorran
              ? `Se borrarán ahora ${seBorran} respuestas guardadas de más de ${elegido} meses. No se puede deshacer; descarga antes una copia si las quieres.`
              : elegido
                ? `A partir de ahora se borrará solo lo que tenga más de ${elegido} meses.`
                : "No se borrará nada de forma automática."}
          </p>
          <div className="flex gap-2">
            <Boton variante="primario" cargando={guardar.isPending} onClick={() => guardar.mutate(elegido ?? null)}>
              {seBorran ? "Borrar y guardar" : "Guardar"}
            </Boton>
            <Boton variante="fantasma" onClick={() => setElegido(undefined)}>
              Cancelar
            </Boton>
          </div>
        </div>
      )}
      {guardar.error && (
        <p role="alert" className="mt-3 text-sm text-peligro">
          {mensaje(guardar.error)}
        </p>
      )}
    </Seccion>
  );
}
