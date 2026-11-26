import { useMutation, useQueryClient } from "@tanstack/react-query";
import { post } from "../api/cliente";
import type { RespuestaConsulta } from "../api/tipos";

/**
 * Pide la línea de tiempo del expediente y la pone arriba del historial de la consola. Si el agente devolvió
 * la guardada (mismo `consultaId`), no se duplica: se sube al principio.
 */
export function useArmarLineaDeTiempo(expedienteId: string, alListo?: () => void) {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (rehacer: boolean) =>
      post<RespuestaConsulta>(`/expedientes/${expedienteId}/cronologia${rehacer ? "?rehacer=true" : ""}`, {}),
    onSuccess: (r) => {
      cliente.setQueryData<RespuestaConsulta[]>(["consultas", expedienteId], (h) => [
        r,
        ...(h ?? []).filter((x) => x.consultaId !== r.consultaId),
      ]);
      alListo?.();
    },
  });
}

/** «Preparar mi cita»: pide el resumen y lo pone arriba del historial de la consola. */
export function usePrepararCita(expedienteId: string, alListo?: () => void) {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: () => post<RespuestaConsulta>(`/expedientes/${expedienteId}/preparacion`, {}),
    onSuccess: (r) => {
      cliente.setQueryData<RespuestaConsulta[]>(["consultas", expedienteId], (h) => [r, ...(h ?? [])]);
      alListo?.();
    },
  });
}
