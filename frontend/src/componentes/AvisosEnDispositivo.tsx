import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/cliente";
import { Bell } from "../iconos";
import { compatibles, suscribir, suscripcionActual } from "../lib/notificaciones";
import { Boton } from "./ui/Boton";

interface EstadoPush {
  disponible: boolean;
  clave_publica: string;
  dispositivos: number;
  por_correo: boolean;
}

const enviar = (metodo: string, ruta: string, cuerpo: unknown) =>
  api<void>(ruta, { method: metodo, body: JSON.stringify(cuerpo) });

/** Avisos de recordatorios en el teléfono o el computador, además del correo o en vez de él. */
export function AvisosEnDispositivo() {
  const puede = compatibles();
  const cliente = useQueryClient();
  const estado = useQuery({ queryKey: ["push"], queryFn: () => api<EstadoPush>("/push"), enabled: puede });
  const aqui = useQuery({ queryKey: ["push-aqui"], queryFn: async () => (await suscripcionActual())?.endpoint ?? null, enabled: puede });
  const refrescar = () =>
    Promise.all([cliente.invalidateQueries({ queryKey: ["push"] }), cliente.invalidateQueries({ queryKey: ["push-aqui"] })]);

  const activar = useMutation({
    mutationFn: async () => {
      const s = await suscribir(estado.data!.clave_publica);
      await enviar("POST", "/push/suscripciones", { endpoint: s.endpoint });
    },
    onSuccess: refrescar,
  });
  const desactivar = useMutation({
    mutationFn: async () => {
      const s = await suscripcionActual();
      if (!s) return;
      await enviar("DELETE", "/push/suscripciones", { endpoint: s.endpoint });
      await s.unsubscribe();
    },
    onSuccess: refrescar,
  });
  const correo = useMutation({
    mutationFn: (por_correo: boolean) => enviar("PUT", "/push/preferencia", { por_correo }),
    onSuccess: refrescar,
  });

  if (!puede || !estado.data?.disponible || aqui.isLoading) return null;
  const error = (activar.error ?? desactivar.error ?? correo.error) as Error | null;
  return (
    <section aria-labelledby="titulo-avisos" className="panel p-5">
      <h2 id="titulo-avisos" className="flex items-center gap-2 text-lg font-semibold">
        <Bell className="size-5 text-primario" aria-hidden />
        Avisos en este dispositivo
      </h2>
      <p className="mt-1 text-sm text-texto-2">
        La notificación solo dice que tienes un recordatorio, sin datos de salud. La entrega el servicio de tu navegador
        (Google, Mozilla, Apple o Microsoft). En iPhone, primero agrega MedTender a la pantalla de inicio.
      </p>
      {error && (
        <p role="alert" className="mt-3 text-sm text-peligro">
          {error.message}
        </p>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-4">
        {aqui.data ? (
          <Boton variante="secundario" tamano="sm" onClick={() => desactivar.mutate()} cargando={desactivar.isPending}>
            Desactivar en este dispositivo
          </Boton>
        ) : (
          <Boton variante="primario" tamano="sm" onClick={() => activar.mutate()} cargando={activar.isPending}>
            Activar avisos en este dispositivo
          </Boton>
        )}
        {estado.data.dispositivos > 0 && (
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input type="checkbox" checked={estado.data.por_correo} onChange={(e) => correo.mutate(e.target.checked)} />
            Avisarme también por correo
          </label>
        )}
      </div>
    </section>
  );
}
