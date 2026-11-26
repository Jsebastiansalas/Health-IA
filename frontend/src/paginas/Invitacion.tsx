import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { post } from "../api/cliente";
import type { CompartidoConmigo } from "../api/tipos";
import { Boton, boton } from "../componentes/ui/Boton";

/**
 * El enlace de la invitación. Nunca se acepta solo: abrir el correo no debe bastar. Sin sesión no se
 * guarda ni se gasta el enlace; se pide entrar con el mismo correo y volver a abrirlo.
 */
export function PaginaInvitacion({ conSesion }: { conSesion: boolean }) {
  const [parametros] = useSearchParams();
  const token = parametros.get("token") ?? "";
  const navegar = useNavigate();
  const cliente = useQueryClient();
  const aceptar = useMutation({
    mutationFn: () => post<CompartidoConmigo>("/invitaciones/aceptar", { token }),
    onSuccess: (c) => {
      void cliente.invalidateQueries({ queryKey: ["compartidos"] });
      navegar(`/expedientes/${c.expediente_id}`, { replace: true });
    },
  });

  return (
    <main className="mx-auto max-w-xl px-4 py-12">
      <h1 className="text-3xl font-semibold">Te invitaron a cuidar un expediente</h1>
      {!token ? (
        <p role="alert" className="mt-4 text-peligro">
          El enlace está incompleto. Ábrelo de nuevo desde el correo de la invitación.
        </p>
      ) : !conSesion ? (
        <>
          <p className="mt-4 leading-relaxed text-texto-2">
            Para aceptarla, ingresa o crea tu cuenta <strong>con el mismo correo</strong> al que llegó la invitación.
            Después, vuelve a abrir el enlace del correo.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/ingreso" className={boton({ variante: "primario" })}>
              Ingresar
            </Link>
            <Link to="/registro" className={boton({ variante: "secundario" })}>
              Crear mi cuenta
            </Link>
          </div>
        </>
      ) : (
        <>
          <p className="mt-4 leading-relaxed text-texto-2">
            Vas a ver información de salud de otra persona. Úsala solo para ayudarle y no la compartas. La persona que te
            invitó verá cuándo entras y puede quitarte el acceso en cualquier momento.
          </p>
          {aceptar.error && (
            <p role="alert" className="mt-4 rounded-xl border border-peligro/35 bg-peligro/10 px-4 py-3 text-sm text-peligro">
              {(aceptar.error as Error).message}
            </p>
          )}
          <div className="mt-6 flex flex-wrap gap-3">
            <Boton variante="primario" onClick={() => aceptar.mutate()} cargando={aceptar.isPending}>
              Aceptar invitación
            </Boton>
            <Link to="/" className={boton({ variante: "fantasma" })}>
              Ahora no
            </Link>
          </div>
        </>
      )}
    </main>
  );
}
