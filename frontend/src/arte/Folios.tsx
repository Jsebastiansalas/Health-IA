import { BadgeCheck, ShieldCheck, Trash2 } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "../lib/cn";

/* Piezas de la portada dibujadas en código con el lenguaje del producto: carpeta manila, folio, resaltador y
   sello. Son la misma interfaz que verá quien ingrese; todo el contenido es de EJEMPLO y está rotulado así. */

/** Sello de goma: rótulo girado y de borde doble, como el que se estampa sobre un folio. */
export function Sello({ children, className, tardanza }: { children: ReactNode; className?: string; tardanza?: string }) {
  return (
    <span
      className={cn(
        "inline-flex -rotate-3 items-center gap-1.5 rounded-[3px] border-2 border-accion px-2.5 py-1 font-display text-[0.8rem] font-bold uppercase tracking-wider text-accion outline outline-1 outline-offset-2 outline-accion/50",
        tardanza && "animate-sello",
        className,
      )}
      style={tardanza ? { animationDelay: tardanza } : undefined}
    >
      {children}
    </span>
  );
}

/**
 * La escena del primer vistazo: una carpeta con el expediente, el folio del pliego con la cláusula marcada y la
 * respuesta con su cita. El resaltador recorre la cláusula y, al final, se estampa «PDF eliminado».
 */
export function EscenaExpediente({ className }: { className?: string }) {
  return (
    <figure className={cn("relative mx-auto w-full max-w-[34rem]", className)} aria-label="Ejemplo ilustrativo de un expediente">
      {/* Carpeta manila detrás */}
      <div aria-hidden className="absolute inset-x-0 top-6 bottom-0 rounded-md bg-carpeta" />
      <div aria-hidden className="absolute left-5 top-0 h-8 w-40 rounded-t-md bg-carpeta" />
      <p className="absolute left-8 top-1.5 font-mono text-[0.72rem] text-tinta" aria-hidden>
        LIC-2027-014
      </p>

      {/* Folio del pliego */}
      <div className="folio relative mx-4 mt-12 p-6 sm:mx-6 sm:p-8">
        <div className="flex items-baseline justify-between gap-4 text-[0.74rem] text-tinta-3">
          <span>Pliego de condiciones</span>
          <span className="num rounded-[3px] border border-tinta/25 px-1.5 font-mono text-tinta-2" title="Folio">
            14
          </span>
        </div>
        <div className="mt-4 space-y-3 font-display text-[1rem] leading-[1.7] text-tinta">
          <p className="text-tinta-2">
            7.2 Las garantías se constituirán a favor de la entidad contratante, y su vigencia se contará desde la firma del contrato.
          </p>
          <p>
            <span className="resaltado-barrido">La garantía de cumplimiento tendrá una vigencia de doce (12) meses</span> contados a partir de la
            entrega y recibo a satisfacción de los bienes.
          </p>
          <p className="text-tinta-3">7.3 En caso de prórroga, el contratista deberá ampliar la vigencia por el mismo término.</p>
        </div>
        <Sello className="absolute -right-2 -top-4 bg-folio sm:right-4" tardanza="2.1s">
          <Trash2 className="size-3.5" aria-hidden />
          PDF eliminado
        </Sello>
      </div>

      {/* La respuesta, apoyada sobre el folio */}
      <div className="folio relative z-10 -mt-6 ml-0 w-[88%] p-4 sm:ml-2">
        <p className="text-[0.76rem] text-tinta-3">¿Qué vigencia tiene la garantía de cumplimiento?</p>
        <p className="mt-1.5 text-[0.95rem] leading-snug">
          Doce (12) meses contados desde la entrega y el recibo a satisfacción{" "}
          <span className="inline-grid h-5 min-w-5 -translate-y-px place-items-center rounded-[3px] bg-marca px-1 align-middle text-[0.68rem] font-bold text-marca-tx">
            1
          </span>
        </p>
        <p className="mt-2.5 flex items-center gap-1.5 font-mono text-[0.68rem] text-tinta-3">
          <BadgeCheck className="size-3.5 text-ok" aria-hidden />
          Pliego · pág. 14 · sha256 9f3a…c41e coincide
        </p>
      </div>
      <figcaption className="mt-3 text-center text-[0.72rem] text-tinta-3">Ejemplo ilustrativo</figcaption>
    </figure>
  );
}

/** El visor local: el documento abierto desde el equipo, con la huella verificada y la cláusula citada. */
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

const FILAS_ACTA: [string, string][] = [
  ["Documento", "Pliego_E2E.pdf"],
  ["Fragmentos indexados", "128 de 128"],
  ["Vectores verificados", "128 de 128"],
  ["Huella SHA-256", "9f3a…c41e"],
  ["Estado del original", "Eliminado"],
];

/** El acta de purga: lo que queda cuando el PDF desaparece del servidor. */
export function ActaPurga({ className }: { className?: string }) {
  return (
    <div className={cn("folio relative p-6 sm:p-8", className)}>
      <p className="text-[0.78rem] text-tinta-3">Acta de purga · ejemplo</p>
      <p className="mt-1 font-display text-[1.5rem] font-semibold leading-tight">Original eliminado del servidor</p>
      <dl className="mt-5 text-[0.88rem]">
        {FILAS_ACTA.map(([k, v]) => (
          <div key={k} className="flex items-baseline justify-between gap-4 border-t border-tinta/12 py-2.5">
            <dt className="text-tinta-2">{k}</dt>
            <dd className="font-mono">{v}</dd>
          </div>
        ))}
      </dl>
      <Sello className="absolute -bottom-3 right-6 bg-folio">
        <Trash2 className="size-3.5" aria-hidden />
        Purgado
      </Sello>
    </div>
  );
}
