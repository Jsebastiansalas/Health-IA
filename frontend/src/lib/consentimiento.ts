import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, post } from "../api/cliente";
import type { EstadoConsentimiento } from "../api/tipos";

const CLAVE = ["consentimiento"];

/** Estado del consentimiento del usuario: solo se exige a las cuentas personales (pacientes y familias). */
export function useConsentimiento() {
  const cliente = useQueryClient();
  const estado = useQuery({
    queryKey: CLAVE,
    queryFn: () => api<EstadoConsentimiento>("/consentimiento"),
    staleTime: 5 * 60_000,
  });
  const aceptar = useMutation({
    mutationFn: () => post<EstadoConsentimiento>("/consentimiento", {}),
    onSuccess: (e) => cliente.setQueryData(CLAVE, e),
  });
  const pendiente = !!estado.data && estado.data.requerido && !estado.data.aceptado;
  return { estado: estado.data, pendiente, aceptar, esPersonal: estado.data?.tipo_cuenta === "PERSONAL" };
}
