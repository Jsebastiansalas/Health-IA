import { BadgeCheck, Trash2 } from "lucide-react";
import { PanelLuz, PlacaPliego } from "./Placa";

/**
 * El mecanismo de MedTender en un negatoscopio: la hoja del pliego entra al panel como placa,
 * se marca el hallazgo con rotulador de cera, se muestra la cita con su huella y la placa se retira:
 * queda la luz vacía y el acta de purga. Ciclo de 14 s; con movimiento reducido se queda en la lectura.
 */
export function Negatoscopio({ className }: { className?: string }) {
  return (
    <div className={className}>
      <PanelLuz className="aspect-[4/5] w-full" luz>
        {/* La placa */}
        <div className="ciclo-placa absolute inset-x-[7%] bottom-[5%] top-[6%] overflow-hidden rounded-[3px] shadow-[0_18px_24px_-14px_rgb(0_0_0/0.7)]">
          <PlacaPliego modo="hallazgo" ciclo />
        </div>

        {/* La cita, leída sobre la placa */}
        <figure className="ciclo-nota absolute inset-x-[10%] bottom-[8%] z-10 rounded-md border border-white/15 bg-[#0a1322] p-3.5 text-tx shadow-[0_18px_28px_-14px_rgb(0_0_0/0.9)] sm:p-4">
          <div className="flex items-center justify-between gap-3">
            <span className="inline-flex items-center gap-1.5 rounded-md border border-ok/35 bg-ok/10 px-2 py-0.5 text-[0.7rem] font-semibold text-ok">
              <BadgeCheck className="size-3.5" aria-hidden />
              Fuente verificada
            </span>
            <span className="etiqueta">ejemplo</span>
          </div>
          <blockquote className="mt-2.5 font-display text-[0.98rem] font-medium leading-snug sm:text-[1.04rem]">
            «La garantía de cumplimiento tendrá una vigencia de doce (12) meses…»
          </blockquote>
          <figcaption className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[0.76rem] text-tx-2">
            <span>Pliego de condiciones · pág. 14</span>
            <span className="font-mono font-semibold text-ok">sha256 9f3a…c41e ✓</span>
          </figcaption>
        </figure>

        {/* El acta, cuando la placa se retira */}
        <div className="ciclo-acta absolute inset-x-[12%] top-[34%] z-10 text-[#0a1322]" aria-hidden>
          <div className="mx-auto max-w-[19rem] rounded-sm border-2 border-[#0a1322] bg-[#f4fafc]/90 px-4 py-3 text-center">
            <Trash2 className="mx-auto size-5" />
            <p className="mt-1 font-display text-[1.05rem] font-extrabold uppercase tracking-[0.12em] [font-stretch:80%]">
              PDF eliminado
            </p>
            <p className="rotulo mt-1 !text-[0.64rem] font-bold">acta de purga · sha256 9f3a…c41e</p>
          </div>
        </div>
      </PanelLuz>

      <p className="rotulo mt-3 flex items-center justify-between text-tx-3">
        <span>Negatoscopio · lectura 1 de 1</span>
        <span>Datos de ejemplo</span>
      </p>
    </div>
  );
}
