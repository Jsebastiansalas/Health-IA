import { HeartPulse, Phone } from "../iconos";
import { cn } from "../lib/cn";

/**
 * Aviso permanente de las pantallas que responden sobre salud. No se puede cerrar: el asistente explica
 * y cita lo que dicen los documentos y las fuentes; no diagnostica, no receta y no atiende urgencias.
 */
export function AvisoSalud({ className }: { className?: string }) {
  return (
    <aside
      aria-label="Aviso sobre el uso del asistente"
      className={cn("flex items-start gap-3 rounded-lg border border-borde bg-panel-2 px-4 py-3 text-xs leading-relaxed text-texto-2", className)}
    >
      <HeartPulse className="mt-0.5 size-4 shrink-0 text-primario" aria-hidden />
      <p>
        <b className="font-semibold text-texto">Información de apoyo, no atención médica.</b> Explica y cita lo que dicen tus documentos y las
        fuentes; no diagnostica ni receta, y no sustituye a un profesional de la salud.{" "}
        <span className="inline-flex items-center gap-1 whitespace-nowrap font-semibold text-texto">
          <Phone className="size-3.5" aria-hidden />
          En una urgencia, llama al 123.
        </span>
      </p>
    </aside>
  );
}

/** Aviso de urgencia que el agente antepone cuando la pregunta describe una posible emergencia. */
export function AvisoUrgencia({ mensaje }: { mensaje: string }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-lg border-2 border-peligro bg-peligro/10 px-4 py-4 text-sm leading-relaxed text-texto">
      <Phone className="mt-1 size-5 shrink-0 text-peligro" aria-hidden />
      <p className="font-medium">{mensaje}</p>
    </div>
  );
}
