import { BookOpenCheck, Eye, FileText, ScrollText } from "lucide-react";
import type { Cita, TipoEvidencia } from "../api/tipos";
import { cn } from "../lib/cn";
import { etiquetaDocumento, paginas } from "../lib/formato";
import { Boton } from "./ui/Boton";
import { Insignia } from "./ui/Insignia";

const METODO: Record<Cita["metodoExtraccion"], string> = {
  NATIVE: "Texto nativo",
  OCR: "OCR",
  MIXED: "Nativo + OCR",
};

/** Etiqueta corta y tono por tipo de evidencia; el motivo completo va debajo. */
const EVIDENCIA: Record<TipoEvidencia, { etiqueta: string; tono: "coral" | "ambar" | "neutro" }> = {
  FIRMA_O_SELLO: { etiqueta: "Firma o sello", tono: "coral" },
  TABLA: { etiqueta: "Tabla", tono: "ambar" },
  IMAGEN: { etiqueta: "Imagen o plano", tono: "ambar" },
  OCR_BAJA_CONFIANZA: { etiqueta: "OCR de baja confianza", tono: "coral" },
  OCR: { etiqueta: "Página escaneada", tono: "neutro" },
};

type Props = {
  cita: Cita;
  numero: number;
  alAbrir: (c: Cita) => void;
  /** Se resalta cuando el usuario pulsa la referencia [n] en la respuesta. */
  resaltada?: boolean;
  id?: string;
};

export function TarjetaCita({ cita, numero, alAbrir, resaltada = false, id }: Props) {
  const adenda = cita.tipoDocumento === "ADENDA";
  return (
    <article
      id={id}
      className={cn(
        "vidrio-solido relative flex flex-col rounded-xl p-4 transition-[box-shadow,border-color] duration-500",
        resaltada && "ring-1 ring-ink/70",
      )}
    >
      <header className="flex items-start gap-3">
        <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-hema/14 font-display text-[0.95rem] font-bold text-hema">
          {numero}
        </span>
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1.5 text-[0.78rem] font-medium text-tx-2">
            {adenda ? <ScrollText className="size-3.5 text-ambar" aria-hidden /> : <FileText className="size-3.5" aria-hidden />}
            <span>
              {etiquetaDocumento(cita.tipoDocumento, cita.numeroAdenda)} · {paginas(cita.paginaInicio, cita.paginaFin)}
            </span>
          </p>
          <p className="truncate font-semibold" title={cita.nombreArchivo}>
            {cita.nombreArchivo}
          </p>
          <p className="truncate text-xs text-tx-3" title={cita.seccion}>
            {cita.seccion}
          </p>
        </div>
      </header>

      <blockquote className="mt-3.5 rounded-lg bg-obsidiana px-3.5 py-3 font-display text-[1.02rem] leading-snug text-tx">
        «{cita.extractoLiteral}»
      </blockquote>

      {cita.requiereVerificacionVisualOriginal && (
        <div className="mt-3 flex items-start gap-2.5 rounded-xl border border-coral/30 bg-coral/10 px-3 py-2.5">
          <Eye className="mt-0.5 size-4 shrink-0 text-coral" aria-hidden />
          <div className="min-w-0 text-xs leading-relaxed text-coral">
            <div className="mb-1.5 flex flex-wrap gap-1.5">
              <Insignia tono="coral" title={cita.motivoVerificacionVisual ?? undefined}>
                Verificar original
              </Insignia>
              {(cita.tiposEvidencia ?? []).map((t) => (
                <Insignia key={t} tono={EVIDENCIA[t].tono}>
                  {EVIDENCIA[t].etiqueta}
                </Insignia>
              ))}
            </div>
            {cita.motivoVerificacionVisual && <p>{cita.motivoVerificacionVisual}</p>}
          </div>
        </div>
      )}

      <footer className="mt-4 flex flex-wrap items-center justify-between gap-2.5">
        <span className="font-mono text-[0.7rem] leading-relaxed text-tx-3">
          {METODO[cita.metodoExtraccion]}
          {cita.confianzaOcr !== null && ` · confianza ${Math.round(cita.confianzaOcr * 100)} %`}
          {cita.extractoAjustado && " · extracto ajustado al texto real"}
        </span>
        <Boton tamano="sm" variante="secundario" onClick={() => alAbrir(cita)}>
          <BookOpenCheck className="size-4 text-hema" aria-hidden />
          Abrir en mi PC · pág. {cita.paginaInicio}
        </Boton>
      </footer>
    </article>
  );
}
