import { BadgeCheck, ShieldCheck } from "lucide-react";
import { cn } from "../lib/cn";

/* Piezas de la portada dibujadas en código con el lenguaje del producto: carpeta manila, folio y resaltador.
   Son la misma interfaz que verá quien ingrese; todo el contenido es de EJEMPLO y está rotulado así. */

/**
 * La escena del primer vistazo: la carpeta de un expediente de dotación biomédica, el folio de una ficha
 * técnica con el requisito marcado y la respuesta con su cita. El resaltador recorre la cláusula una vez.
 */
export function EscenaExpediente({ className }: { className?: string }) {
  return (
    <figure className={cn("relative mx-auto w-full max-w-[34rem]", className)} aria-label="Ejemplo ilustrativo de una consulta sobre una licitación de equipos biomédicos">
      {/* Carpeta manila detrás */}
      <div aria-hidden className="absolute inset-x-0 top-6 bottom-0 rounded-md bg-carpeta" />
      <div aria-hidden className="absolute left-5 top-0 h-8 w-56 rounded-t-md bg-carpeta" />
      <p className="absolute left-8 top-1.5 font-mono text-[0.72rem] text-tinta" aria-hidden>
        DOT-2027-003 · Equipos biomédicos
      </p>

      {/* Folio de la ficha técnica */}
      <div className="folio relative mx-4 mt-12 p-6 sm:mx-6 sm:p-8">
        <div className="flex items-baseline justify-between gap-4 text-[0.74rem] text-tinta-3">
          <span>Ficha técnica · Monitor multiparámetro</span>
          <span className="num rounded-[3px] border border-tinta/25 px-1.5 font-mono text-tinta-2" title="Folio">
            6
          </span>
        </div>
        <div className="mt-4 space-y-3 font-display text-[1rem] leading-[1.7] text-tinta">
          <p className="text-tinta-2">
            3.1 El equipo deberá monitorear electrocardiograma, saturación de oxígeno y presión arterial no invasiva en pacientes adultos y pediátricos.
          </p>
          <p>
            <span className="resaltado-barrido">El oferente deberá acreditar registro sanitario INVIMA vigente y certificado de calibración</span> del
            equipo ofertado.
          </p>
          <p className="text-tinta-3">3.3 La garantía técnica no será inferior a veinticuatro (24) meses.</p>
        </div>
      </div>

      {/* La respuesta, apoyada sobre el folio */}
      <div className="folio relative z-10 -mt-6 ml-0 w-[88%] p-4 sm:ml-2">
        <p className="text-[0.76rem] text-tinta-3">¿Qué debe acreditar el oferente del monitor?</p>
        <p className="mt-1.5 text-[0.95rem] leading-snug">
          Registro sanitario INVIMA vigente y certificado de calibración del equipo{" "}
          <span className="inline-grid h-5 min-w-5 -translate-y-px place-items-center rounded-[3px] bg-marca px-1 align-middle text-[0.68rem] font-bold text-marca-tx">
            1
          </span>
        </p>
        <p className="mt-2.5 flex items-center gap-1.5 font-mono text-[0.68rem] text-tinta-3">
          <BadgeCheck className="size-3.5 text-ok" aria-hidden />
          Ficha técnica · pág. 6 · fuente verificada
        </p>
      </div>
      <figcaption className="mt-3 text-center text-[0.72rem] text-tinta-3">Ejemplo ilustrativo</figcaption>
    </figure>
  );
}

/** El visor local: el documento abierto desde el equipo, con la huella verificada y el requisito citado. */
export function VisorDocumento({ className }: { className?: string }) {
  return (
    <div className={cn("folio p-6 text-left sm:p-8", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2 text-[0.76rem]">
        <span className="text-tinta-3">Abierto desde tu equipo</span>
        <span className="inline-flex items-center gap-1.5 font-medium text-ok">
          <ShieldCheck className="size-3.5" aria-hidden />
          SHA-256 coincide
        </span>
      </div>
      <p className="mt-3 font-display text-[1.2rem] font-semibold">Pliego de condiciones · pág. 14</p>
      <div className="mt-4 space-y-3 font-display text-[0.98rem] leading-[1.7] text-tinta-2">
        <p>
          7.2 Las garantías se constituirán a favor de la entidad contratante, y su vigencia se contará desde la firma del contrato.{" "}
          <span className="resaltado">La garantía de cumplimiento tendrá una vigencia de doce (12) meses</span> contados a partir de la
          entrega y recibo a satisfacción de los bienes.
        </p>
        <p>7.3 En caso de prórroga, el contratista deberá ampliar la vigencia de la garantía por el mismo término.</p>
      </div>
      <p className="mt-5 border-t border-tinta/12 pt-3 font-mono text-[0.7rem] text-tinta-3">
        registrado 9f3a…c41e · en tu equipo 9f3a…c41e · ejemplo
      </p>
    </div>
  );
}
