import type { Cita } from "../api/tipos";
import { etiquetaDocumento, paginas } from "../lib/formato";

const METODO: Record<Cita["metodoExtraccion"], string> = {
  NATIVE: "Texto nativo",
  OCR: "OCR",
  MIXED: "Nativo + OCR",
};

export function TarjetaCita({ cita, numero, alAbrir }: { cita: Cita; numero: number; alAbrir: (c: Cita) => void }) {
  const adenda = cita.tipoDocumento === "ADENDA";
  return (
    <article
      className={`folio relative animate-aparecer border-l-4 p-4 ${adenda ? "border-l-sello" : "border-l-tinta"}`}
      style={{ animationDelay: `${numero * 70}ms` }}
    >
      <header className="flex items-start gap-3">
        <span className="font-display text-3xl leading-none text-grafito">{numero}</span>
        <div className="min-w-0 flex-1">
          <p className="etiqueta">
            {etiquetaDocumento(cita.tipoDocumento, cita.numeroAdenda)} · {paginas(cita.paginaInicio, cita.paginaFin)}
          </p>
          <p className="truncate font-medium" title={cita.nombreArchivo}>{cita.nombreArchivo}</p>
          <p className="truncate text-xs text-tinta-2" title={cita.seccion}>{cita.seccion}</p>
        </div>
        {cita.requiereVerificacionVisualOriginal && (
          <span className="sello shrink-0 text-sello" title={cita.motivoVerificacionVisual ?? undefined}>
            Verificar original
          </span>
        )}
      </header>

      <blockquote className="mt-3 border-l border-papel-3 pl-3 font-display text-[1.02rem] leading-snug italic text-tinta-2">
        «{cita.extractoLiteral}»
      </blockquote>

      {cita.requiereVerificacionVisualOriginal && cita.motivoVerificacionVisual && (
        <p className="mt-3 text-xs text-sello">{cita.motivoVerificacionVisual}</p>
      )}

      <footer className="mt-4 flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-[0.66rem] text-grafito">
          {METODO[cita.metodoExtraccion]}
          {cita.confianzaOcr !== null && ` · confianza ${Math.round(cita.confianzaOcr * 100)} %`}
          {cita.extractoAjustado && " · extracto ajustado al texto real"}
        </span>
        <button className="boton boton-linea !px-3 !py-1.5 text-xs" onClick={() => alAbrir(cita)}>
          Abrir en mi PC · pág. {cita.paginaInicio}
        </button>
      </footer>
    </article>
  );
}
