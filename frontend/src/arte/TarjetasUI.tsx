import { ArrowUp, BadgeCheck, FileUp, ShieldCheck, Trash2 } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "../lib/cn";

/* Piezas de interfaz del producto dibujadas para la bienvenida: son la misma interfaz que verá la persona
   al ingresar. Superficies de grafito planas, sin sombra. Todo el contenido es de ejemplo. */

/** Superficie de grafito: un paso más clara que el lienzo, sin borde ni sombra. */
export function Grafito({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("rounded-xl bg-panel text-tx", className)}>{children}</div>;
}

const marca = "rounded-[3px] bg-ink/[0.16] px-0.5 text-tx";

/** La consulta: pregunta, respuesta con referencia [1] y la cita con su huella. */
export function VentanaConsulta({ className }: { className?: string }) {
  return (
    <Grafito className={cn("p-5 text-left", className)}>
      <div className="flex items-center justify-between">
        <p className="text-[0.8rem] text-tx-2">Consulta · LIC-2027-014</p>
        <span className="etiqueta">ejemplo</span>
      </div>
      <p className="ml-auto mt-4 w-fit max-w-[90%] rounded-2xl rounded-tr-sm bg-obsidiana px-4 py-2.5 text-[0.88rem] leading-snug">
        ¿Qué dice la adenda 2 sobre el plazo de entrega?
      </p>
      <p className="mt-4 text-[0.9rem] leading-relaxed text-tx">
        La <span className={marca}>Adenda N° 2</span> modifica el plazo: será de <b className="font-medium">quince (15) días calendario</b>{" "}
        <span className="inline-grid size-[1.15rem] -translate-y-px place-items-center rounded-full bg-ink text-[0.66rem] font-medium text-sala align-middle">1</span>.
      </p>
      <div className="mt-4 rounded-xl bg-obsidiana p-3.5">
        <span className="inline-flex items-center gap-1.5 text-[0.7rem] text-ok">
          <BadgeCheck className="size-3.5" aria-hidden />
          Fuente verificada
        </span>
        <p className="mt-2 text-[0.84rem] leading-snug">«El plazo de entrega será de quince (15) días calendario.»</p>
        <p className="mt-2 font-mono text-[0.68rem] text-tx-3">Adenda 2 · pág. 1 · sha256 9f3a…c41e ✓</p>
      </div>
      <div className="mt-4 flex items-center justify-between rounded-full border border-ink/40 py-1.5 pl-5 pr-1.5 text-[0.84rem] text-tx-3">
        Pregunta a tu expediente
        <span className="grid size-8 place-items-center rounded-full bg-cobalto text-white">
          <ArrowUp className="size-4" aria-hidden />
        </span>
      </div>
    </Grafito>
  );
}

/** El visor local: el documento abierto desde el equipo, con la cláusula citada marcada. */
export function VisorDocumento({ className }: { className?: string }) {
  return (
    <Grafito className={cn("p-5 text-left", className)}>
      <div className="flex items-center justify-between gap-2 text-[0.72rem]">
        <span className="text-tx-3">Abierto desde tu equipo</span>
        <span className="inline-flex items-center gap-1 text-ok">
          <ShieldCheck className="size-3.5" aria-hidden />
          SHA-256 coincide
        </span>
      </div>
      <p className="mt-3 font-display text-[1.05rem] font-[480] [font-stretch:112%]">Pliego de condiciones · pág. 14</p>
      <div className="mt-3 space-y-2.5 text-[0.82rem] leading-relaxed text-tx-2">
        <p>
          7.2 Las garantías se constituirán a favor de la entidad contratante, y su vigencia se contará desde la firma del contrato.{" "}
          <span className={marca}>La garantía de cumplimiento tendrá una vigencia de doce (12) meses</span> contados a partir de la entrega y
          recibo a satisfacción de los bienes.
        </p>
        <p>7.3 En caso de prórroga, el contratista deberá ampliar la vigencia de la garantía por el mismo término.</p>
      </div>
    </Grafito>
  );
}

const FILAS: { cod: string; tit: string; est: string; ok?: boolean }[] = [
  { cod: "LIC-2027-014", tit: "Suministro de medicamentos oncológicos", est: "Indexado y purgado", ok: true },
  { cod: "DOT-2027-003", tit: "Dotación de equipos de imagenología", est: "Extrayendo OCR" },
  { cod: "AUD-2027-021", tit: "Auditoría de glosas, nivel II", est: "Indexado y purgado", ok: true },
];

/** La lista de expedientes con el estado del pipeline. */
export function ListaExpedientes({ className }: { className?: string }) {
  return (
    <Grafito className={cn("overflow-hidden text-left", className)}>
      <p className="px-5 pb-1 pt-4 text-[0.78rem] text-tx-3">Expedientes</p>
      <ul>
        {FILAS.map((f) => (
          <li key={f.cod} className="flex items-center gap-3 px-5 py-3">
            <span className={cn("size-1.5 shrink-0 rounded-full", f.ok ? "bg-ok" : "bg-tx-3")} aria-hidden />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[0.84rem]">{f.tit}</span>
              <span className="block truncate font-mono text-[0.66rem] text-tx-3">
                {f.cod} · {f.est}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </Grafito>
  );
}

/** El aviso de purga: el momento en que el PDF desaparece. */
export function AvisoPurga({ className }: { className?: string }) {
  return (
    <div className={cn("inline-flex items-center gap-2.5 rounded-full bg-obsidiana py-2 pl-2.5 pr-5 text-[0.84rem] text-tx", className)}>
      <span className="grid size-6 place-items-center rounded-full bg-ink text-sala">
        <Trash2 className="size-3.5" aria-hidden />
      </span>
      PDF eliminado · acta de purga
    </div>
  );
}

/** Zona de carga: el primer paso. */
export function ZonaCarga({ className }: { className?: string }) {
  return (
    <div className={cn("grid place-items-center rounded-xl border border-dashed border-ink/35 px-4 py-8 text-center", className)}>
      <FileUp className="size-6 text-tx-2" strokeWidth={1.5} aria-hidden />
      <p className="mt-3 text-[0.9rem]">Suelta los PDF del expediente</p>
      <p className="mt-0.5 text-[0.76rem] text-tx-3">o elígelos desde tu equipo</p>
    </div>
  );
}
