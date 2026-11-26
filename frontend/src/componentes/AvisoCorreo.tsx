import { MailCheck } from "../iconos";
import { Boton } from "./ui/Boton";

/** Cuenta personal con el correo sin confirmar: no puede subir ni consultar hasta abrir el enlace que se le envió. */
export function AvisoCorreo({
  reenviando,
  reenviado,
  error,
  alReenviar,
}: {
  reenviando: boolean;
  reenviado: boolean;
  error?: string;
  alReenviar: () => void;
}) {
  return (
    <section aria-labelledby="titulo-correo" className="panel mb-8 p-6 sm:p-8">
      <h2 id="titulo-correo" className="flex items-center gap-3 text-xl">
        <MailCheck className="size-6 text-primario" aria-hidden />
        Confirma tu correo
      </h2>
      <p className="mt-2 max-w-2xl text-texto-2">
        Te enviamos un enlace al registrarte. Ábrelo para activar tu cuenta: hasta entonces no puedes subir documentos ni hacer consultas. Si no
        lo encuentras, revisa la carpeta de correo no deseado o pide uno nuevo.
      </p>
      {error && (
        <p role="alert" className="mt-3 text-sm text-peligro">
          {error}
        </p>
      )}
      {reenviado && (
        <p role="status" className="mt-3 text-sm text-ok">
          Enviamos un enlace nuevo.
        </p>
      )}
      <div className="mt-4">
        <Boton onClick={alReenviar} cargando={reenviando}>
          Reenviar enlace
        </Boton>
      </div>
    </section>
  );
}
