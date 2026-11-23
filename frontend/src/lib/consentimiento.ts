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
  const reenviar = useMutation({ mutationFn: () => post<void>("/auth/reenviar-verificacion", {}) });
  const pendiente = !!estado.data && estado.data.requerido && !estado.data.aceptado;
  const correoPendiente = !!estado.data && estado.data.correo_requerido && !estado.data.correo_verificado;
  return {
    estado: estado.data,
    pendiente,
    /** Sin confirmar el correo no se sube ni se consulta (el servidor responde 403 `correo_no_verificado`). */
    correoPendiente,
    /** Cualquiera de las dos exigencias bloquea subir y consultar. */
    bloqueado: pendiente || correoPendiente,
    aceptar,
    reenviar,
    esPersonal: estado.data?.tipo_cuenta === "PERSONAL",
  };
}
