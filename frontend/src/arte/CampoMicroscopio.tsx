import { BadgeCheck, Trash2 } from "lucide-react";
import { Insignia } from "../componentes/ui/Insignia";
import { BarraEscala } from "./Decoracion";
import { HojaDisuelta } from "./HojaDisuelta";
import { Tejido } from "./Tejido";

/**
 * El campo de un microscopio con el mecanismo de MedTender dentro: la hoja del pliego se deshace
 * en células del tejido, una de ellas queda señalada con su anotación y la hoja desaparece.
 * Ocular graduado, barril oscuro, retículo en cruz, barra de escala y aumento, como en una micrografía.
 */
export function CampoMicroscopio() {
  return (
    <div className="relative mx-auto aspect-square w-full max-w-[42rem]">
      {/* Graduación del ocular */}
      <div className="graticula absolute -inset-[1.5%] rounded-full opacity-70" aria-hidden />

      {/* Barril y campo de visión */}
      <div className="absolute inset-[2%] overflow-hidden rounded-full border-[10px] border-hema-pro shadow-[0_40px_80px_-30px_rgb(28_23_82/0.7),inset_0_0_40px_rgb(28_23_82/0.35)]">
        <Tejido semilla={11} celula={50} tinte={1} lavanda={0.4} />
        <div
          className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,transparent_55%,rgb(28_23_82/0.28)_100%)]"
          aria-hidden
        />
        {/* Retículo */}
        <div className="absolute inset-x-0 top-1/2 h-px bg-ink/25" aria-hidden />
        <div className="absolute inset-y-0 left-1/2 w-px bg-ink/25" aria-hidden />
        <div className="absolute left-1/2 top-1/2 size-16 -translate-x-1/2 -translate-y-1/2 rounded-full border border-ink/25" aria-hidden />
        <div className="absolute inset-[7%]">
          <HojaDisuelta className="absolute inset-0" />
        </div>
        <BarraEscala micras={50} className="absolute bottom-[11%] left-[16%] rounded-md bg-white/80 px-2 py-1.5" />
        <span className="absolute right-[14%] top-[12%] rounded-md bg-white/80 px-2 py-1 font-mono text-[0.78rem] font-bold text-ink">
          ×40
        </span>
      </div>

      {/* Rótulo del portaobjetos */}
      <div className="absolute -left-[1%] top-[3%] -rotate-3 rounded-md border border-ink/20 bg-white px-3 py-1.5 font-mono text-[0.72rem] leading-snug text-ink shadow-[0_8px_18px_-10px_rgb(28_23_82/0.5)]">
        <span className="font-bold">Pliego_E2E.pdf</span>
        <br />
        sección 1 de 3 · tinción H&amp;E
      </div>

      {/* Sello: aparece cuando la hoja se deshace. */}
      <div className="absolute left-[10%] top-[44%] w-[34%] text-center">
        <div className="ciclo-sello mx-auto inline-flex rotate-[-4deg] flex-col items-center gap-1 rounded-2xl border-[3px] border-eosina bg-white/90 px-4 py-2.5 text-eosina-osc shadow-[0_10px_24px_-12px_rgb(217_48_111/0.7)]">
          <Trash2 className="size-5" aria-hidden />
          <span className="font-display text-[0.95rem] font-extrabold uppercase leading-none tracking-wider">PDF eliminado</span>
          <span className="font-mono text-[0.66rem] font-semibold">acta de purga · SHA-256</span>
        </div>
      </div>

      {/* La anotación de la célula citada. */}
      <figure className="ciclo-cita vidrio-solido absolute bottom-[0%] right-[-3%] w-[58%] rounded-2xl p-4 text-left sm:p-5">
        <div className="mb-2.5 flex items-center justify-between gap-2">
          <Insignia tono="ok">
            <BadgeCheck className="size-3.5" aria-hidden />
            Fuente verificada
          </Insignia>
          <span className="etiqueta">ejemplo</span>
        </div>
        <blockquote className="font-display text-[0.98rem] font-medium leading-snug text-ink sm:text-[1.05rem]">
          «La garantía de cumplimiento tendrá una vigencia de doce (12) meses…»
        </blockquote>
        <figcaption className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.78rem] text-tx-2">
          <span>Pliego de condiciones · pág. 2</span>
          <span className="font-mono font-semibold text-ok">sha256 9f3a…c41e ✓</span>
        </figcaption>
      </figure>
    </div>
  );
}
