import { BookOpenCheck, Eye, FileText, ScrollText } from "../iconos";
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
const EVIDENCIA: Record<TipoEvidencia, { etiqueta: string; tono: "peligro" | "aviso" | "neutro" }> = {
  FIRMA_O_SELLO: { etiqueta: "Firma o sello", tono: "peligro" },
  TABLA: { etiqueta: "Tabla", tono: "aviso" },
  IMAGEN: { etiqueta: "Imagen o plano", tono: "aviso" },
  OCR_BAJA_CONFIANZA: { etiqueta: "OCR de baja confianza", tono: "peligro" },
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

/**
 * La cita es la pieza central del producto: un fragmento del panel original con el texto citado
 * resaltado, su procedencia exacta (documento, página, sección) y lo que el texto extraído no puede
 * garantizar. El número es el mismo marcador amarillo que lleva la referencia [n] en la respuesta.
 */
export function TarjetaCita({ cita, numero, alAbrir, resaltada = false, id }: Props) {
  const adenda = cita.tipoDocumento === "ADENDA";
  return (
    <article
      id={id}
      className={cn("panel relative flex flex-col p-4 transition-shadow duration-500", resaltada && "ring-2 ring-cita")}
    >
      <header className="flex items-start gap-3">
        <span
          className="grid size-6 shrink-0 place-items-center rounded-md bg-cita text-xs font-semibold text-cita-tx"
          aria-label={`Cita ${numero}`}
        >
          {numero}
        </span>
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 text-xs font-medium text-texto-2">
            {adenda ? <ScrollText className="size-3.5 text-aviso" aria-hidden /> : <FileText className="size-3.5" aria-hidden />}
            <span>
              {etiquetaDocumento(cita.tipoDocumento, cita.numeroAdenda)} · {paginas(cita.paginaInicio, cita.paginaFin)}
            </span>
          </p>
          <p className="truncate font-semibold" title={cita.nombreArchivo}>
            {cita.nombreArchivo}
          </p>
        </div>
      </header>

      <blockquote className="mt-3 text-base leading-[1.75] text-texto">
        <span className="resaltado">«{cita.extractoLiteral}»</span>
      </blockquote>
      <p className="mt-2 truncate text-xs text-texto-3" title={cita.seccion}>
        {cita.seccion}
      </p>

      {cita.requiereVerificacionVisualOriginal && (
        <div className="mt-3 border-t border-borde pt-3">
          <div className="flex flex-wrap items-center gap-2">
            <Insignia tono="peligro" title={cita.motivoVerificacionVisual ?? undefined}>
              <Eye className="size-3.5" aria-hidden />
              Verificar original
            </Insignia>
            {(cita.tiposEvidencia ?? []).map((t) => (
              <Insignia key={t} tono={EVIDENCIA[t].tono}>
                {EVIDENCIA[t].etiqueta}
              </Insignia>
            ))}
          </div>
          {cita.motivoVerificacionVisual && (
            <p className="mt-2 text-xs leading-relaxed text-texto-2">{cita.motivoVerificacionVisual}</p>
          )}
        </div>
      )}

      <footer className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <span className="font-mono text-xs leading-relaxed text-texto-3">
          {METODO[cita.metodoExtraccion]}
          {cita.confianzaOcr !== null && ` · confianza ${Math.round(cita.confianzaOcr * 100)} %`}
          {cita.extractoAjustado && " · extracto ajustado al texto real"}
          <span className="block" title={`SHA-256 ${cita.sha256Original}`}>
            sha256 {cita.sha256Original.slice(0, 10)}…
          </span>
        </span>
        <Boton tamano="sm" variante="secundario" onClick={() => alAbrir(cita)}>
          <BookOpenCheck className="size-4 text-primario" aria-hidden />
          Abrir en mi PC · pág. {cita.paginaInicio}
        </Boton>
      </footer>
    </article>
  );
}
